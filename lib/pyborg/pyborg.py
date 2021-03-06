# -*- coding: utf-8 -*-
# vim: set sw=4 sts=4 ts=8 et:
"""
# PyBorg: The python AI bot.
#
# Copyright (c) 2000, 2006 Tom Morton, Sebastien Dailly
#
#
# This bot was inspired by the PerlBorg, by Eric Bock.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# Tom Morton <tom@moretom.net>
# Seb Dailly <seb.dailly@gmail.com>
"""

import random
import sys
import os
import marshal    # buffered marshal is bloody fast. wish i'd found this before :)
import struct
import time
import zipfile
import math
import string
import re
import json
import gspread
import datetime
from decimal import Decimal
from oauth2client.client import SignedJwtAssertionCredentials
from pprint import pprint
from atomicfile import AtomicFile


def filter_message(message, bot):
    """
    Filter a message body so it is suitable for learning from and
    replying to. This involves removing confusing characters,
    padding ? and ! with ". " so they also terminate lines
    and converting to lower case.
    """


    # to lowercase
    message = message.lower()

    # remove garbage
    message = message.replace("\"", "") # remove "s
    #message = message.replace("'", "") # remove 's
    message = message.replace("\n", " ") # remove newlines
    message = message.replace("\r", " ") # remove carriage returns

    # remove matching brackets (unmatched ones are likely smileys :-) *cough*
    # should except out when not found.
    index = 0
    try:
        while 1:
            index = message.index("(", index)
            # Remove matching) bracket
            i = message.index(")", index + 1)
            message = message[0:i] + message[i + 1:]
            # And remove the (
            message = message[0:index] + message[index + 1:]
    except ValueError:
        pass

    # No sense in keeping URLS
        message = re.sub(r"https?://[^ ]* ", "", message)

    message = message.replace("; ", ", ")
    for split_char in ['?', '!', '.', ',']:
        message = message.replace(split_char, " %c " % split_char)
#    message = message.replace("'", " ' ")
#    message = re.sub(r"\b:", " : ", message)
#    message = message.replace("#nick:", "#nick :")

    # Find ! and ? and append full stops.
#    message = message.replace(". ", ".. ")
#    message = message.replace("? ", "?. ")
#    message = message.replace("! ", "!. ")

    #And correct the '...'
#    message = message.replace("..  ..  .. ", ".... ")

    words = message.split()
    if bot.settings.process_with == "pyborg":
        for x in xrange(0, len(words)):
            #is there aliases ?
            for z in bot.settings.aliases.keys():
                for alias in bot.settings.aliases[z]:
                    pattern = "^%s$" % alias
                    if re.search(pattern, words[x]):
                        words[x] = z

    clean = lambda x: ''.join(filter(string.printable.__contains__, x))

    message = clean(" ".join(words))
    try:
        message.encode('utf-8')
    except Exception, e:
        print "Could not parse %r: %s" % (message, str(e))
        raise e

    return message.encode("utf-8")


class pyborg:
    import cfgfile

    ver_string = "I am a version 1.1.2 PyBorg"
    saves_version = "1.1.0"

    saving = False
    bot_name = "Pyborg"

    # Main command list
    commandlist = "Pyborg commands:\n!checkdict, !contexts, !help, !known, !learning, !rebuilddict, \
!replace, !unlearn, !purge, !version, !words, !limit, !alias, !save, !censor, !uncensor, !owner"
    commanddict = {
        "help": "Owner command. Usage: !help [command]\nPrints information about using a command, or a list of commands if no command is given",
        "version": "Usage: !version\nDisplay what version of Pyborg we are running",
        "words": "Usage: !words\nDisplay how many words are known",
        "known": "Usage: !known word1 [word2 [...]]\nDisplays if one or more words are known, and how many contexts are known",
        "contexts": "Owner command. Usage: !contexts <phrase>\nPrint contexts containing <phrase>",
        "unlearn": "Owner command. Usage: !unlearn <expression>\nRemove all occurances of a word or expression from the dictionary. For example '!unlearn of of' would remove all contexts containing double 'of's",
        "purge": "Owner command. Usage: !purge [number]\nRemove up to <number> words that appears in less than 2 contexts. Specify 0 to see how many are eligible to remove.",
        "replace": "Owner command. Usage: !replace <old> <new>\nReplace all occurances of word <old> in the dictionary with <new>",
        "learning": "Owner command. Usage: !learning [on|off]\nToggle bot learning. Without arguments shows the current setting",
        "checkdict": "Owner command. Usage: !checkdict\nChecks the dictionary for broken links. Shouldn't happen, but worth trying if you get KeyError crashes",
        "rebuilddict": "Owner command. Usage: !rebuilddict\nRebuilds dictionary links from the lines of known text. Takes a while. You probably don't need to do it unless your dictionary is very screwed",
        "censor": "Owner command. Usage: !censor [word1 [...]]\nPrevent the bot using one or more words. Without arguments lists the currently censored words",
        "uncensor": "Owner command. Usage: !uncensor word1 [word2 [...]]\nRemove censorship on one or more words",
        "limit": "Owner command. Usage: !limit [number]\nSet the number of words that pyBorg can learn",
        "alias": "Owner command. Usage: !alias : Show the differents aliases\n!alias <alias> : show the words attached to this alias\n!alias <alias> <word> : link the word to the alias",
        "owner": "Usage : !owner password\nAdd the user in the owner list"
    }

    def __init__(self):
        """
        Open the dictionary. Resize as required.
        """
        # Attempt to load settings
        self.settings = self.cfgfile.cfgset()
        self.settings.load("pyborg.cfg",
            { "num_contexts": ("Total word contexts", 0),
              "num_words":    ("Total unique words known", 0),
              "max_words":    ("max limits in the number of words known", 6000),
              "learning":    ("Allow the bot to learn", 1),
              "ignore_list":("Words that can be ignored for the answer", ['!.', '?.', "'", ',', ';']),
              "censored":    ("Don't learn the sentence if one of those words is found", []),
              "num_aliases":("Total of aliases known", 0),
              "aliases":    ("A list of similars words", {}),
              "process_with":("Wich way for generate the reply (pyborg|megahal)", "pyborg"),
              "no_save"    :("If True, Pyborg don't saves the dictionary and configuration on disk", "False")
            })

        self.answers = self.cfgfile.cfgset()
        self.answers.load("answers.txt",
            { "sentences":    ("A list of prepared answers", {})
            })
        self.unfilterd = {}

        #Set up google credentials
        json_key = json.loads(open("google_auth.json").read())

        #load system data
        system_data = json.loads(open("systems.json").read())
        self.system_data = {x['name'].lower() : x for x in system_data}

        self.oauth_creds = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), ['https://spreadsheets.google.com/feeds'])

        self.frog_data = {
            'the_form' : {
                    'id' : '1r1bCFOroZ1FJ_02ZmBmOaZwAybBakDj1hOXt43nVH40',
                    'sheets' : {
                        'responses' : {'id' : 'okrb2x6', 'data' : None},
                        'processed' : {'id' : 'o7ao2pc', 'data' : None},
                        },
                    },
            'goatcore' : {
                    'id' : '1-MRZ0CT-NSzOstnbuMMjbHH79vzr5FfiNboMvDqICGo',
                    'sheets' : {
                        'deployments' : {'id' : 'olhqcx7', 'data' : None},
                        'anurans' : {'id' : 'o3yggcj', 'data' : None},
                        'pollywogs' : {'id' : 'odz817l', 'data' : None},
                        'euro frogs' : {'id' : 'o33tuhd', 'data' : None},
                        'reserves' : {'id' : 'o7hxgb1', 'data' : None},
                        'iff registry' : {'id' : 'oxi9gng', 'data' : None},
                        'command staff' : {'id' : 'otieqhn', 'data' : None},
                        'deployments' : {'id' : 'olhqcx7', 'data' : None},
                        'organizations' : {'id' : 'o1j4hnl', 'data' : None},
                        },
                    },
        }
        self.wing_data = {}
        self.frog_list = {}
        self.not_frogs = {}
        self.other_orgs = {}

        self.scramble_reports = {}

        self.deploy_data = {}

        self.last_data_update = None

        # Read the dictionary
        if self.settings.process_with == "pyborg":
            print "Reading dictionary..."
            try:
                zfile = zipfile.ZipFile('archive.zip', 'r')
                for filename in zfile.namelist():
                    data = zfile.read(filename)
                    data_file = open(filename, 'w+b')
                    data_file.write(data)
                    data_file.close()
            except (EOFError, IOError):
                print "no zip found"
            try:

                content = self.read_file("version")
                os.unlink('version')
                if content != self.saves_version:
                    print "Error loading dictionary\Please convert it before launching pyborg"
                    sys.exit(1)

                content = self.read_file("words.dat")
                os.unlink('words.dat')
                self.words = marshal.loads(content)
                del content
                content = self.read_file("lines.dat")
                os.unlink('lines.dat')
                self.lines = marshal.loads(content)
                del content
            except (EOFError, IOError):
                # Create mew database
                self.words = {}
                self.lines = {}
                print "Error reading saves. New database created."

            # Is a resizing required?
            if len(self.words) != self.settings.num_words:
                print "Updating dictionary information..."
                self.settings.num_words = len(self.words)
                num_contexts = 0
                # Get number of contexts
                for x in self.lines.keys():
                    num_contexts += len(self.lines[x][0].split())
                self.settings.num_contexts = num_contexts
                # Save new values
                self.settings.save()

            # Is an aliases update required ?
            compteur = 0
            for x in self.settings.aliases.keys():
                compteur += len(self.settings.aliases[x])
            if compteur != self.settings.num_aliases:
                print "check dictionary for new aliases"
                self.settings.num_aliases = compteur

                for x in self.words.keys():
                    #is there aliases ?
                    if x[0] != '~':
                        for z in self.settings.aliases.keys():
                            for alias in self.settings.aliases[z]:
                                pattern = "^%s$" % alias
                                if self.re.search(pattern, x):
                                    print "replace %s with %s" % (x, z)
                                    self.replace(x, z)

                for x in self.words.keys():
                    if not (x in self.settings.aliases.keys()) and x[0] == '~':
                        print "unlearn %s" % x
                        self.settings.num_aliases -= 1
                        self.unlearn(x)
                        print "unlearned aliases %s" % x


            #unlearn words in the unlearn.txt file.
            try:
                f = open("unlearn.txt", "r")
                while 1:
                    word = f.readline().strip('\n')
                    if word == "":
                        break
                    if self.words.has_key(word):
                        self.unlearn(word)
                f.close()
            except (EOFError, IOError):
                # No words to unlearn
                pass

        self.settings.save()

    @staticmethod
    def read_file(file_name):
        """ Return the content of a File
        """
        with open(file_name, 'rb') as f:
            return f.read()

    ##
    # Saves all dictionaries and words and contexts, everything.
    # @return returns true if successfully saved, or false if it failed.
    def save_all(self):
        if self.saving:
            print "Cannot save because currently saving."
            return False
        else:
            self.saving = True
            try:
                if self.settings.process_with == "pyborg" and self.settings.no_save != "True":
                    print "Writing dictionary..."

                    with zipfile.ZipFile('archive.zip', 'w',
                                         zipfile.ZIP_DEFLATED) as z:
                        s = marshal.dumps(self.words)
                        z.writestr('words.dat', s)
                        s = marshal.dumps(self.lines)
                        z.writestr('lines.dat', s)
                        #save the version
                        z.writestr('version', self.saves_version)

                    for filename, data in [
                                            ('words.txt', self.words),
                                            ('sentences.txt', self.unfilterd),
                                          ]:
                        with AtomicFile(filename, 'w') as f:
                            # write each words known
                            wordlist = []
                            #Sort the list befor to export
                            for key in data.keys():
                                wordlist.append([key, len(data[key])])
                            wordlist.sort(lambda x, y: cmp(x[1], y[1]))
                            #map((lambda x: f.write(str(x[0]) + "\n\r")), wordlist)
                            [ f.write(str(x[0]) + "\n\r") for x in wordlist]

                    # Save settings
                    self.settings.save()

                    print "Dictionary saved."
                    return True
            finally:
                self.saving = False

    def process_msg(self, io_module, body, replyrate, learn, args, owner = False, cmd_resp = False, ctxt_resp = False, opsec_level = None):
        """
        Process message 'body' and pass back to IO module with args.
        If owner==1 allow owner commands.
        """

        try:
            if self.settings.process_with == "megahal":
                import mh_python
        except:
            self.settings.process_with = "pyborg"
            self.settings.save()
            print "Could not find megahal python library\nProgram ending"
            sys.exit(1)

        # add trailing space so sentences are broken up correctly
        #body = body + " "

        #Check for contextual commands
        contextual = self.is_contextual_command(body)
        if contextual and ctxt_resp:
            #print "It's a contextual command:"
            contextual[1](io_module, contextual[0], args, owner, opsec_level=opsec_level)
            #pprint(contextual)
            return

        # Parse commands
        if body[0] == "!" and cmd_resp:
            self.do_commands(io_module, body, args, owner, opsec_level=opsec_level)
            return

        # Filter out garbage and do some formatting
        body = filter_message(body, self)
        body = body.replace(self.bot_name.lower(), '')

        # Learn from input
        if learn == True:
            if self.settings.process_with == "pyborg":
                self.learn(body)
            elif self.settings.process_with == "megahal" and self.settings.learning == 1:
                mh_python.learn(body)


        # Make a reply if desired
        if random.randint(0, 99) < replyrate:

            message = ""

            #Look if we can find a prepared answer
            for sentence in self.answers.sentences.keys():
                pattern = "^%s$" % sentence
                if re.search(pattern, body):
                    message = self.answers.sentences[sentence][random.randint(0, len(self.answers.sentences[sentence]) - 1)]
                    break
                else:
                    if body in self.unfilterd:
                        self.unfilterd[body] = self.unfilterd[body] + 1
                    else:
                        self.unfilterd[body] = 0

            if message == "":
                if self.settings.process_with == "pyborg":
                    potential_replies = []
                    potential_replies = [self.reply(body) for x in range(0,3)]
                    #print "Got some potential replies:"
                    pprint(potential_replies)

                    message = potential_replies[0]

                    if len(message) < len(potential_replies[1]):
                        message = potential_replies[1]

                    if len(message) < len(potential_replies[2]):
                        message = potential_replies[2]

                    #message = self.reply(body)
                elif self.settings.process_with == "megahal":
                    message = mh_python.doreply(body)

            # single word reply: never output
            if len(message.split()) == 1:
                #io_module.output(message, args)
                return
            # empty. do not output
            if message == "":
                return
            # else output
            io_module.output(message, args)

    def is_contextual_command(self, body):
        """
        Check to see if a given chat line is a contextual argument.
        """

        command_list = {
                '^who(?: the fuck)? is (?:cmdr )?((?:\w+\s?){1,3})$' : self.identify_friend_foe,
                '^(witness m[ey].*)$' : self.witness,
                '^where is (.+)$' : self.distance_to_home,
                }

        #if re.search(pattern, words[x]):
        for regex in command_list.keys():
            result = re.match(regex, body, re.I)
            if result:
                return (result.group(1), command_list[regex])

        return False

    def distance_to_home(self, io_module, body, args, owner, opsec_level=None):

        home_key = "63 G. Capricorni"
        if body.lower() in self.system_data.keys():
            payload = {'distance' : self.distance_between(body, home_key.lower()), 'source' : home_key, 'dest' : self.system_data[body.lower()]['name']}
            msg = "%(dest)s is %(distance)1.2fly from %(source)s" % payload
        else:
            msg = "I don't know where %s is" % body

        io_module.output(msg, args)




    def distance_between(self, key_a, key_b):
        """
        Calculates the distance between two known systems
        """
        key_a = key_a.lower()
        key_b = key_b.lower()
        if not key_a in self.system_data.keys() or not key_b in self.system_data.keys():
            return False

        sys_a_x = Decimal(self.system_data[key_a]['x'])
        sys_a_y = Decimal(self.system_data[key_a]['y'])
        sys_a_z = Decimal(self.system_data[key_a]['z'])

        sys_b_x = Decimal(self.system_data[key_b]['x'])
        sys_b_y = Decimal(self.system_data[key_b]['y'])
        sys_b_z = Decimal(self.system_data[key_b]['z'])

        x_len = sys_b_x - sys_a_x
        y_len = sys_b_y - sys_a_y
        z_len = sys_b_z - sys_a_z

        hyp_1 = math.sqrt(math.pow(x_len, 2) + math.pow(y_len, 2))
        hyp_2 = math.sqrt(math.pow(z_len, 2) + math.pow(hyp_1, 2))

        return hyp_2



    def witness(self, io_module, body, args, owner, opsec_level=None):
        """
        Mediocre!
        """
        check = random.randint(0, 10)
        if check == 0:
            message = "PERFECT IN EVERY WAY!"
            #message = "http://fi.somethingawful.com/safs/smilies/4/f/perfect.001.gif"
        #elif check == 1:
        #    message = "http://fi.somethingawful.com/safs/smilies/d/2/dunkedon.001.gif"
        else:
            #message = "http://fi.somethingawful.com/safs/smilies/f/9/mediocre.001.gif"
            message = "MEDIOCRE!"

        io_module.output(message, args)

    def _update_frog_data(self):
        gc = gspread.authorize(self.oauth_creds)
        wks = gc.openall()
        for doc in wks:
            for exp_doc in self.frog_data:
                if doc.id == self.frog_data[exp_doc]['id']:
                    #exp_doc['data'] = doc
                    for sheet in doc.worksheets():
                        for exp_sheet in self.frog_data[exp_doc]['sheets']:
                            if sheet.id == self.frog_data[exp_doc]['sheets'][exp_sheet]['id']:
                                self.frog_data[exp_doc]['sheets'][exp_sheet]['data'] = sheet.get_all_values()

        self.wing_data = {}
        self.frog_list = {}
        for flight in self.frog_data['goatcore']['sheets']:
            if flight in ['anurans','pollywogs','euro frogs','reserves']:
                wing_list = zip(*self.frog_data['goatcore']['sheets'][flight]['data'])


                for wing_data in wing_list:
                    self.wing_data[wing_data[0].strip()] = [x.strip() for x in wing_data[1:] if x != ""]

                    #fancy_flight_name = wing_data[0]
                    if wing_data[0][-2] == "1":
                        fancy_flight_name = "%sth" % wing_data[0]
                    elif wing_data[0][-1] == "1":
                        fancy_flight_name = "%sst" % wing_data[0]
                    elif wing_data[0][-1] == "2":
                        fancy_flight_name = "%snd" % wing_data[0]
                    elif wing_data[0][-1] == "3":
                        fancy_flight_name = "%srd" % wing_data[0]
                    else:
                        fancy_flight_name = "%sth" % wing_data[0]


                    for f in self.wing_data[wing_data[0]]:
                        self.frog_list[f.lower()] = {'name' : f, 'rank' : 'a member', 'flight' : fancy_flight_name, 'squadron' : flight, 'flight_number' : wing_data[0]}

                    if wing_data[1] != "":
                        self.frog_list[wing_data[1].lower()]['rank'] = 'the flight leader'
                #for f_num in self.frog_data['goatcore']['sheets'][flight]['data']:
                    #self.wing_data[f_num] = {'lead' : '', 'members' : []}
                #Flight #s are self.frog_data['goatcore']['sheets'][flight]['data'][0]
                #Flight leads are self.frog_data['goatcore']['sheets'][flight]['data'][1]
            elif flight in ['command staff']:
                wing_list = self.frog_data['goatcore']['sheets'][flight]['data']
                for member in wing_list[0:]:
                    self.frog_list[member[0].lower()] = {'name' : member[0], 'rank' : member[1], 'flight' : '', 'flight_number' : ''}

        self.not_frogs = {x[0] : x[1:] for x in zip(*self.frog_data['goatcore']['sheets']['iff registry']['data'])}

        self.other_orgs = {x[0] : {'level' : x[1], 'members' : [y for y in x[2:] if y != ""]} for x in zip(*self.frog_data['goatcore']['sheets']['organizations']['data'])}

        for item in self.scramble_reports.keys():
            if abs(self.scramble_reports[item]['time'] - datetime.datetime.now()).seconds > 300:
                del self.scramble_reports[item]

        deploy_data = zip(*self.frog_data['goatcore']['sheets']['deployments']['data'])

        self.deploy_data = {}
        for item in deploy_data[2:]:
            target = item[0]
            self.deploy_data.update({x : target for x in item[1:] if x != ""})

        self.last_data_update = datetime.datetime.now()

    def identify_friend_foe(self, io_module, body, args, owner, opsec_level=None):
        """
        Module to search for and store IFF information.
        """

        #Opsec level for this is 0 or higher
        if opsec_level is None:
            return


        raw_body, source, target, msg_type = args

        #Refresh frog_data every 600 seconds
        if self.last_data_update is None:
            io_module.output("Registering IFF signatures, stand by.", args)
            self._update_frog_data()

        body = body.strip()
        check = body.lower().strip()
        if len(check) < 3:
            return

        #if check == "darthblingbling":
        #    io_module.kick("ARE YOU QUESTIONING YOUR SUPERIORS", args)

        if check == "frogbear":
            io_module.set_role("I Didn't Ask For This", args[1], args)
            io_module.output("We are Frog. We are Bear. The barriers between us have fallen and we have become our own shadows. We can be more if we join...with you.", args)
            #io_module.output("I'm a strong black woman who don't need no form. And you're an ass.", args)
            return

        #HAAAACK
        try:
            #wks = gc.openall()
            #iff = wks[0].worksheets()[1].get_all_values()
            potential_frogs = []

            message = {}

            line_items = self.frog_data['the_form']['sheets']['processed']['data']
            #pprint(self.frog_list)

            if line_items is None:
                raise Exception("IFF data not loaded.")

            for frog in line_items:
                #1: SA Name
                #2: CMDR Name
                #3: Inara Name
                if check in frog[1].lower() or check in frog[2].lower() or check in frog[3].lower():
                    postfix = ""
                    prefix = ""
                    #if frog[1].lower() != frog[2].lower():
                    #    postfix = ", aka on the forums as %s" % frog[1]

                    if frog[2].lower() in self.frog_list:
                        this_frog = self.frog_list[frog[2].lower()]
                        if this_frog['flight'] != "":
                            prefix = "CMDR %s is %s of the %s %s" % (frog[2], this_frog['rank'], this_frog['flight'], this_frog['squadron'])
                        else:
                            prefix = "CMDR %s is the %s" % (frog[2], this_frog['rank'])
                    else:
                        prefix = "CMDR %s is a registered Frog" % frog[2]

                    postfix = []
                    if frog[2].lower() != frog[1].lower() and frog[1] != "":
                        postfix.append("SA: **%s**" % frog[1])

                    if frog[2].lower() != frog[3].lower() and frog[3] != "":
                        postfix.append("Inara: **%s**" % frog[3])

                    if len(postfix) > 0:
                        postfix = " (%s)" % ", ".join(postfix)
                    else:
                        postfix = ""


                    #message.append(prefix + postfix)
                    message[frog[2].lower()] = {'type' : 'frog', 'message' : prefix + postfix + "."}

            for frog in self.frog_list.keys():
                if check in frog.lower() and frog.lower() not in message.keys():
                    if self.frog_list[frog]['flight'] == "":
                        msg = "CMDR %s is the %s" % (self.frog_list[frog]['name'], self.frog_list[frog]['rank'])
                    else:
                        msg = "CMDR %s is %s of the %s %s" % (self.frog_list[frog]['name'], self.frog_list[frog]['rank'], self.frog_list[frog]['flight'], self.frog_list[frog]['squadron'])

                    message[frog.lower()] = {'type' : 'frog', 'message' : msg + ", and needs to fill out the damn form."}

            #CMDR X is a MISSION TARGET/KOS affiliated with ORG. !scramble to etc
            #CMDR X is a MISSION TARGET/KOS. Advising friendly affiliation with ORG, engage with discretion. !scramble to etc

            for org in self.other_orgs.keys():
                this_org = self.other_orgs[org]
                for member in this_org['members']:
                    if check in member.lower():
                        msg = { 'message' : "CMDR %s is affiliated with %s" % (member, org), 'org' : {'name' : org}, 'cmdr' : member}
                        if this_org['level'] == "Friendly":
                            msg['org']['type'] = "friendly"
                            msg['type'] = "friendly"
                            msg['message'] += " and is *FRIENDLY*."
                        elif this_org['level'] == "Hostile":
                            msg['org']['type'] = "mission_target"
                            msg['type'] = "mission_target"
                            msg['message'] += " and is a **MISSION TARGET**."
                        elif this_org['level'] == "KOS":
                            msg['message'] += " and is **KOS**."
                            msg['org']['type'] = "kos"
                            msg['type'] = "kos"
                        else:
                            msg['org']['type'] = "neutral"
                            msg['type'] = ""

                        message[member.lower()] = msg
                        break


            for kos in self.not_frogs['KOS']:
                if check in kos.lower():
                    #message.append("CMDR %s is a KOS target. Type \"!scramble <location>\" to alert the fleet." % kos)
                    if kos.lower() in message:
                        msg = "CMDR %s is a **KOS TARGET**" % kos
                        if message[kos.lower()]['type'] == "friendly":
                            msg = msg + ". Advising friendly affiliation with %s, engage with discretion." % message[kos.lower()]['org']['name']
                        else:
                            msg = msg + " affiliated with %s." % message[kos.lower()]['org']['name']

                        message[kos.lower()].update({'message' : msg, 'type' : 'kos'})
                    else:
                        message[kos.lower()] = {'message' : "CMDR %s is a KOS target." % kos, 'type' : 'kos', 'cmdr' : kos}

                        #self.scramble_reports[source] = {
                        #        'reporter' : source,
                        #        'target' : kos,
                        #        'orig_channel' : '1b-gunfrogs-kos-alerts',
                        #        'time' : datetime.datetime.now()
                        #        }

            for mission_target in self.not_frogs['Mission Target']:
                if check in mission_target.lower():
                    #message.append("CMDR %s is a mission_target target. Type \"!scramble <location>\" to alert the fleet." % mission_target)
                    if mission_target.lower() in message:
                        msg = "CMDR %s is a **MISSION TARGET**" % mission_target
                        if message[mission_target.lower()]['type'] == "friendly":
                            msg = msg + ". Advising friendly affiliation with %s, engage with discretion." % message[mission_target.lower()]['org']['name']
                        else:
                            msg = msg + " affiliated with %s." % message[mission_target.lower()]['org']['name']

                        message[mission_target.lower()].update({'message' : msg, 'type' : "mission_target"})
                    else:
                        message[mission_target.lower()] = {'message' : "CMDR %s is a **MISSION TARGET**." % mission_target, 'type' : 'mission_target', 'cmdr' : mission_target}

                    #message[mission_target.lower()] = "CMDR %s is a mission target. Type \"!scramble <location>\" to alert %s" % (mission_target, target.name)
                    #message.append("CMDR %s is a mission target. Type \"!scramble <location>\" to alert the fleet." % mission_target)
                    #self.scramble_reports[source] = {
                    #        'reporter' : source,
                    #        'target' : mission_target,
                    #        'orig_channel' : target.name,
                    #        'time' : datetime.datetime.now()
                    #        }

            for friendly in self.not_frogs['Non-Frog Friendly']:
                if check in friendly.lower():
                    #CMDR X is a FRIENDLY affiliated with ORG.
                    #CMDR X is a FRIENDLY. Advising enemy affiliation ORG, engage with discretion. !scramble to etc

                    if friendly.lower() in message:
                        if message[friendly.lower()]['type'] in ['mission_target', 'kos']:
                            msg = "CMDR %s is a *KNOWN FRIENDLY*. Advising enemy affiliation with %s, engage with discretion." % (friendly, message[friendly.lower()]['org']['name'])
                    else:
                        message[friendly.lower()] = {'type' : 'friendly', 'message' : "CMDR %s is a *KNOWN FRIENDLY*." % friendly, 'cmdr' : friendly}

                    #message.append("CMDR %s is a Non-Frog Friendly." % friendly)

            if len(message.keys()) > 3:
                io_module.output("Too many results found", args)
            elif len(message.keys()) > 0:
                #TODO: Whitelist people immune from assing.
                #if 'darthblingbling' in message.keys():
                #    message['darthblingbling'] = message['darthblingbling'] + " Also, you're an ass."
                #    io_module.set_role("Dumb Arsehole", args[1], args)


                for m in message:
                    print "Outputting %s" % message[m]
                    if message[m]['type'] in ["mission_target", "kos"]:
                        message[m]['message'] = message[m]['message'] + " Type \"!scramble <location>\" to alert the fleet."

                        channel = target.name
                        if message[m]['type'] == "kos":
                            channel = "1b-gunfrogs-kos-alerts"

                        self.scramble_reports[source] = {
                                'reporter' : source,
                                'target' : message[m]['cmdr'],
                                'orig_channel' : channel,
                                'time' : datetime.datetime.now()
                                }

                    io_module.output(message[m]['message'], args)
            else:
                io_module.output("No IFF data registered for %s." % body, args)

        except Exception, e:
            print "Horrible exception thrown: %s" % str(e)
            io_module.output("Could not retrieve IFF data for %s." % body, args)
            raise

        if abs(datetime.datetime.now() - self.last_data_update).seconds > 600:
            #io_module.output("Updating IFF signatures.", args)
            self._update_frog_data()

    def orders(self, io_module, body, args, owner, opsec_level=None):
        """
        Scramble the fleet
        """
        if opsec_level is None:
            return

        raw_body, source, target, msg_type = args

        #Refresh frog_data every 600 seconds
        if self.last_data_update is None or abs(datetime.datetime.now() - self.last_data_update).seconds > 600:
            io_module.output("Updating IFF signatures, stand by.", args)
            self._update_frog_data()


        #TODO: Bind frog names to shit
        if source.lower() in self.frog_list:
            if self.frog_list[source.lower()]['flight_number'] != "":
                if self.frog_list[source.lower()]['flight_number'] in self.deploy_data:
                    msg = "You are assigned to %s" % self.deploy_data[self.frog_list[source.lower()]['flight_number']]
                else:
                    msg = "Could not find your flight's deploy data. Assume Standing Orders until further notice."
            else:
                msg = "Could not find your flight. Contact your flight leader for further instructions."
        else:
            msg = "Could not match your Discord name to a Frog. Contact your flight leader for current orders."

        io_module.output(msg, (raw_body, source, source, "private"))

    def scramble(self, io_module, body, args, owner, opsec_level=None):
        """
        Scramble the fleet
        """
        if opsec_level is None:
            return

        raw_body, source, target, msg_type = args

        for p_scram in self.scramble_reports.keys():
            if abs(datetime.datetime.now() - self.scramble_reports[p_scram]['time']).seconds > 300:
                del self.scramble_reports[p_scram]
            elif self.scramble_reports[p_scram]['reporter'] == source:
                io_module.output("@everyone Scramble! %s reported in %s by %s" % (self.scramble_reports[p_scram]['target'], body, self.scramble_reports[p_scram]['reporter']), (raw_body, source, self.scramble_reports[p_scram]['orig_channel'], "public"))
                del self.scramble_reports[p_scram]

    def do_commands(self, io_module, body, args, owner, opsec_level=None):
        """
        Respond to user comands.
        """
        msg = ""

        command_list = body.split()
        command_list[0] = command_list[0].lower()

        # Guest commands.
        body, source, target, msg_type = args

        # Version string
        if command_list[0] == "!version":
            msg = self.ver_string

        elif command_list[0] == "!recache":
            if owner or source.lower() in ['paramemetic']:
                io_module.output("Updating IFF signatures, standby.", args)
                self._update_frog_data()
                msg = "Update complete."
            else:
                return

        elif command_list[0] in ["!iff", "!w"]:
            self.identify_friend_foe(io_module, " ".join(command_list[1:]), args, owner, opsec_level=opsec_level)
            return
        elif command_list[0] == "!scramble":
            self.scramble(io_module, " ".join(command_list[1:]), args, owner, opsec_level=opsec_level)
            return
        elif command_list[0] == "!orders":
            self.orders(io_module, " ".join(command_list[1:]), args, owner, opsec_level=opsec_level)
            return
        elif command_list[0] == "!distance":
            try:
                #print "Attempting to split %s" % command_list
                split = command_list.index("to")
                system_1 = " ".join(command_list[1:split])
                system_2 = " ".join(command_list[split+1:])
                #print "Systems recorded as %s, %s" % (system_1, system_2)
                distance = self.distance_between(system_1, system_2)
                payload = {'distance' : distance, 'source' : self.system_data[system_1.lower()]['name'], 'dest' : self.system_data[system_2.lower()]['name']}
                #print "Distance is %s" % distance
                if distance:
                    msg = "%(dest)s is %(distance)1.2fly from %(source)s" % payload
                    #msg = "It's %1.2fly from %s to %s" % (distance, self.system_data[system_1.lower()]['name'], self.system_data[system_2.lower()]['name'])
                else:
                    raise Exception
            except Exception, e:
                print "Exception raised: %s" % str(e)
                msg = "Could not find both systems requested."
            #self.orders(io_module, " ".join(command_list[1:]), args, owner, opsec_level=opsec_level)

        # How many words do we know?
        elif command_list[0] == "!words" and self.settings.process_with == "pyborg":
            num_w = self.settings.num_words
            num_c = self.settings.num_contexts
            num_l = len(self.lines)
            if num_w != 0:
                num_cpw = num_c / float(num_w) # contexts per word
            else:
                num_cpw = 0.0
            msg = "I know %d words (%d contexts, %.2f per word), %d lines." % (num_w, num_c, num_cpw, num_l)

        # Do i know this word
        elif command_list[0] == "!known" and self.settings.process_with == "pyborg":
            words = (x.lower() for x in command_list[1:])
            msg = "Number of contexts: "
            for word in words:
                if self.words.has_key(word):
                    contexts = len(self.words[word])
                    msg += word + "/%i " % contexts
                else:
                    msg += word + "/unknown "
            msg = msg.replace("#nick", "$nick")

        # Owner commands
        if owner == True:
            # Save dictionary

            if command_list[0] == "!save":
                if self.save_all():
                    msg = "Dictionary saved"
                else:
                    msg = "Already saving"

            # Command list
            elif command_list[0] == "!help":
                if len(command_list) > 1:
                    # Help for a specific command
                    cmd = command_list[1].lower()
                    dic = None
                    if cmd in self.commanddict.keys():
                        dic = self.commanddict
                    elif cmd in io_module.commanddict.keys():
                        dic = io_module.commanddict
                    if dic:
                        for i in dic[cmd].split("\n"):
                            io_module.output(i, args)
                    else:
                        msg = "No help on command '%s'" % cmd
                else:
                    for i in self.commandlist.split("\n"):
                        io_module.output(i, args)
                    for i in io_module.commandlist.split("\n"):
                        io_module.output(i, args)

            # Change the max_words setting
            elif command_list[0] == "!limit" and self.settings.process_with == "pyborg":
                msg = "The max limit is "
                if len(command_list) == 1:
                    msg += str(self.settings.max_words)
                else:
                    limit = int(command_list[1].lower())
                    self.settings.max_words = limit
                    msg += "now " + command_list[1]


            # Check for broken links in the dictionary
            elif command_list[0] == "!checkdict" and self.settings.process_with == "pyborg":
                t = time.time()
                num_broken = 0
                num_bad = 0
                for w in self.words.keys():
                    wlist = self.words[w]

                    for i in xrange(len(wlist) - 1, -1, -1):
                        if len(wlist[i]) == 10:
                            line_idx, word_num = struct.unpack("qH", wlist[i])
                        else:
                            line_idx, word_num = struct.unpack("lH", wlist[i])

                        # Nasty critical error we should fix
                        if not self.lines.has_key(line_idx):
                            print "Removing broken link '%s' -> %d" % (w, line_idx)
                            num_broken = num_broken + 1
                            del wlist[i]
                        else:
                            # Check pointed to word is correct
                            split_line = self.lines[line_idx][0].split()
                            if split_line[word_num] != w:
                                print "Line '%s' word %d is not '%s' as expected." % \
                                    (self.lines[line_idx][0],
                                    word_num, w)
                                num_bad = num_bad + 1
                                del wlist[i]
                    if len(wlist) == 0:
                        del self.words[w]
                        self.settings.num_words = self.settings.num_words - 1
                        print "\"%s\" vaped totally" % w

                msg = "Checked dictionary in %0.2fs. Fixed links: %d broken, %d bad." % \
                    (time.time() - t,
                    num_broken,
                    num_bad)

            # Rebuild the dictionary by discarding the word links and
            # re-parsing each line
            elif command_list[0] == "!rebuilddict" and self.settings.process_with == "pyborg":
                if self.settings.learning == 1:
                    t = time.time()

                    old_lines = self.lines
                    old_num_words = self.settings.num_words
                    old_num_contexts = self.settings.num_contexts

                    self.words = {}
                    self.lines = {}
                    self.settings.num_words = 0
                    self.settings.num_contexts = 0

                    for k in old_lines.keys():
                        self.learn(old_lines[k][0], old_lines[k][1])

                    msg = "Rebuilt dictionary in %0.2fs. Words %d (%+d), contexts %d (%+d)" % \
                            (time.time() - t,
                            old_num_words,
                            self.settings.num_words - old_num_words,
                            old_num_contexts,
                            self.settings.num_contexts - old_num_contexts)

            #Remove rares words
            elif command_list[0] == "!purge" and self.settings.process_with == "pyborg":
                t = time.time()

                liste = []
                compteur = 0

                if len(command_list) == 2:
                # limite d occurences a effacer
                    c_max = command_list[1].lower()
                else:
                    c_max = 0

                c_max = int(c_max)

                for w in self.words.keys():

                    digit = 0
                    char = 0
                    for c in w:
                        if c.isalpha():
                            char += 1
                        if c.isdigit():
                            digit += 1


                #Compte les mots inferieurs a cette limite
                    c = len(self.words[w])
                    if c < 2 or (digit and char):
                        liste.append(w)
                        compteur += 1
                        if compteur == c_max:
                            break

                if c_max < 1:
                    #io_module.output(str(compteur)+" words to remove", args)
                    io_module.output("%s words to remove" % compteur, args)
                    return

                #supprime les mots
                [self.unlearn(w) for w in liste[0:]]


                msg = "Purge dictionary in %0.2fs. %d words removed" % \
                        (time.time() - t,
                        compteur)

            # Change a typo in the dictionary
            elif command_list[0] == "!replace" and self.settings.process_with == "pyborg":
                if len(command_list) < 3:
                    return
                old = command_list[1].lower()
                new = command_list[2].lower()
                msg = self.replace(old, new)

            # Print contexts [flooding...:-]
            elif command_list[0] == "!contexts" and self.settings.process_with == "pyborg":
                # This is a large lump of data and should
                # probably be printed, not module.output XXX

                # build context we are looking for
                context = " ".join(command_list[1:])
                context = context.lower()
                if context == "":
                    return
                io_module.output("Contexts containing \"" + context + "\":", args)
                # Build context list
                # Pad it
                context = " " + context + " "
                c = []
                # Search through contexts
                for x in self.lines.keys():
                    # get context
                    ctxt = self.lines[x][0]
                    # add leading whitespace for easy sloppy search code
                    ctxt = " " + ctxt + " "
                    if ctxt.find(context) != -1:
                        # Avoid duplicates (2 of a word
                        # in a single context)
                        if len(c) == 0:
                            c.append(self.lines[x][0])
                        elif c[len(c) - 1] != self.lines[x][0]:
                            c.append(self.lines[x][0])
                x = 0
                while x < 5:
                    if x < len(c):
                        io_module.output(c[x], args)
                    x += 1
                if len(c) == 5:
                    return
                if len(c) > 10:
                    io_module.output("...(" + `len(c) - 10` + " skipped)...", args)
                x = len(c) - 5
                if x < 5:
                    x = 5
                while x < len(c):
                    io_module.output(c[x], args)
                    x += 1

            # Remove a word from the vocabulary [use with care]
            elif command_list[0] == "!unlearn" and self.settings.process_with == "pyborg":
                # build context we are looking for
                context = " ".join(command_list[1:])
                context = context.lower()
                if context == "":
                    return
                print "Looking for: " + context
                # Unlearn contexts containing 'context'
                t = time.time()
                self.unlearn(context)
                # we don't actually check if anything was
                # done..
                msg = "Unlearn done in %0.2fs" % (time.time() - t)

            # Query/toggle bot learning
            elif command_list[0] == "!learning":
                msg = "Learning mode "
                if len(command_list) == 1:
                    if self.settings.learning == 0:
                        msg += "off"
                    else:
                        msg += "on"
                else:
                    toggle = command_list[1].lower()
                    if toggle == "on":
                        msg += "on"
                        self.settings.learning = 1
                    else:
                        msg += "off"
                        self.settings.learning = 0

            # add a word to the 'censored' list
            elif command_list[0] == "!censor" and self.settings.process_with == "pyborg":
                # no arguments. list censored words
                if len(command_list) == 1:
                    if len(self.settings.censored) == 0:
                        msg = "No words censored"
                    else:
                        msg = "I will not use the word(s) %s" % ", ".join(self.settings.censored)
                # add every word listed to censored list
                else:
                    for x in xrange(1, len(command_list)):
                        if command_list[x] in self.settings.censored:
                            msg += "%s is already censored" % command_list[x]
                        else:
                            self.settings.censored.append(command_list[x].lower())
                            self.unlearn(command_list[x])
                            msg += "done"
                        msg += "\n"

            # remove a word from the censored list
            elif command_list[0] == "!uncensor" and self.settings.process_with == "pyborg":
                # Remove everyone listed from the ignore list
                # eg !unignore tom dick harry
                for x in xrange(1, len(command_list)):
                    try:
                        self.settings.censored.remove(command_list[x].lower())
                        msg = "done"
                    except ValueError:
                        pass

            elif command_list[0] == "!alias" and self.settings.process_with == "pyborg":
                # no arguments. list aliases words
                if len(command_list) == 1:
                    if len(self.settings.aliases) == 0:
                        msg = "No aliases"
                    else:
                        msg = "I will alias the word(s) %s" \
                        % ", ".join(self.settings.aliases.keys())
                # add every word listed to alias list
                elif len(command_list) == 2:
                    if command_list[1][0] != '~': command_list[1] = '~' + command_list[1]
                    if command_list[1] in self.settings.aliases.keys():
                        msg = "Thoses words : %s  are aliases to %s" \
                        % (" ".join(self.settings.aliases[command_list[1]]), command_list[1])
                    else:
                        msg = "The alias %s is not known" % command_list[1][1:]
                elif len(command_list) > 2:
                    #create the aliases
                    msg = "The words : "
                    if command_list[1][0] != '~': command_list[1] = '~' + command_list[1]
                    if not(command_list[1] in self.settings.aliases.keys()):
                        self.settings.aliases[command_list[1]] = [command_list[1][1:]]
                        self.replace(command_list[1][1:], command_list[1])
                        msg += command_list[1][1:] + " "
                    for x in xrange(2, len(command_list)):
                        msg += "%s " % command_list[x]
                        self.settings.aliases[command_list[1]].append(command_list[x])
                        #replace each words by his alias
                        self.replace(command_list[x], command_list[1])
                    msg += "have been aliases to %s" % command_list[1]

            # Quit
            elif command_list[0] == "!quit":
                # Close the dictionary
                self.save_all()
                sys.exit()

            # Save changes
            self.settings.save()

        if msg != "":
            io_module.output(msg, args)

    def replace(self, old, new):
        """
        Replace all occuraces of 'old' in the dictionary with
        'new'. Nice for fixing learnt typos.
        """
        try:
            pointers = self.words[old]
        except KeyError:
            return old + " not known."
        changed = 0

        for x in pointers:
            # pointers consist of (line, word) to self.lines
            if len(x) == 10:
                l, w = struct.unpack("qH", x)
            else:
                l, w = struct.unpack("lH", x)
            line = self.lines[l][0].split()
            number = self.lines[l][1]
            if line[w] != old:
                # fucked dictionary
                print "Broken link: %s %s" % (x, self.lines[l][0])
                continue
            else:
                line[w] = new
                self.lines[l][0] = " ".join(line)
                self.lines[l][1] += number
                changed += 1

        if self.words.has_key(new):
            self.settings.num_words -= 1
            self.words[new].extend(self.words[old])
        else:
            self.words[new] = self.words[old]
        del self.words[old]
        return "%d instances of %s replaced with %s" % (changed, old, new)

    def unlearn(self, context):
        """
        Unlearn all contexts containing 'context'. If 'context'
        is a single word then all contexts containing that word
        will be removed, just like the old !unlearn <word>
        """
        # Pad thing to look for
        # We pad so we don't match 'shit' when searching for 'hit', etc.
        context = " " + context + " "
        # Search through contexts
        # count deleted items
        dellist = []
        # words that will have broken context due to this
        wordlist = []
        for x in self.lines.keys():
            # get context. pad
            c = " " + self.lines[x][0] + " "
            if c.find(context) != -1:
                # Split line up
                wlist = self.lines[x][0].split()
                # add touched words to list
                for w in wlist:
                    if not w in wordlist:
                        wordlist.append(w)
                dellist.append(x)
                del self.lines[x]
        words = self.words
        # update links
        for x in wordlist:
            word_contexts = words[x]
            # Check all the word's links (backwards so we can delete)
            for y in xrange(len(word_contexts) - 1, -1, -1):
                # Check for any of the deleted contexts
                if len(word_contexts[y]) == 10:
                    unpacked = struct.unpack( "qH", word_contexts[y] )[0]
                else:
                    unpacked = struct.unpack( "lH", word_contexts[y] )[0]
                if unpacked in dellist:
                    del word_contexts[y]
                    self.settings.num_contexts = self.settings.num_contexts - 1
            if len(words[x]) == 0:
                del words[x]
                self.settings.num_words = self.settings.num_words - 1
                print "\"%s\" vaped totally" % x

    def reply(self, body):
        """
        Reply to a line of text.
        """
        # split sentences into list of words
        _words = body.split(" ")
        words = []
        for i in _words:
            words += i.split()
        del _words

        if len(words) == 0:
            return ""

        #remove words on the ignore list
        #words = filter((lambda x: x not in self.settings.ignore_list and not x.isdigit()), words)
        words = (x for x in words if x not in self.settings.ignore_list and not x.isdigit())

        # Find rarest word (excluding those unknown)
        index = []
        known = -1
        #The word has to be seen in already 3 contexts differents for being choosen
        known_min = 3
        for x in  words:
            if self.words.has_key(x):
                k = len(self.words[x])
            else:
                continue
            if (known == -1 or k < known) and k > known_min:
                index = [x]
                known = k
                continue
            elif k == known:
                index.append(x)
                continue
        # Index now contains list of rarest known words in sentence
        if len(index) == 0:
            return ""
        word = index[random.randint(0, len(index) - 1)]

        # Build sentence backwards from "chosen" word
        sentence = [word]
        done = 0
        while done == 0:
            #create a dictionary wich will contain all the words we can found before the "chosen" word
            pre_words = {"" : 0}
            #this is for prevent the case when we have an ignore_listed word
            word = str(sentence[0].split(" ")[0])
            for x in xrange(0, len(self.words[word]) - 1):
                if len(self.words[word][x]) == 10:
                    l, w = struct.unpack("qH", self.words[word][x])
                else:
                    l, w = struct.unpack("lH", self.words[word][x])
                context = self.lines[l][0]
                num_context = self.lines[l][1]
                cwords = context.split()
                #if the word is not the first of the context, look the previous one
                if cwords[w] != word:
                    print context
                if w:
                    #look if we can found a pair with the choosen word, and the previous one
                    if len(sentence) > 1 and len(cwords) > w + 1:
                        if sentence[1] != cwords[w + 1]:
                            continue

                    #if the word is in ignore_list, look the previous word
                    look_for = cwords[w - 1]
                    if look_for in self.settings.ignore_list and w > 1:
                        look_for = cwords[w - 2] + " " + look_for

                    #saves how many times we can found each word
                    if not(pre_words.has_key(look_for)):
                        pre_words[look_for] = num_context
                    else :
                        pre_words[look_for] += num_context

                else:
                    pre_words[""] += num_context

            #Sort the words
            liste = pre_words.items()
            liste.sort(lambda x, y: cmp(y[1], x[1]))

            numbers = [liste[0][1]]
            for x in xrange(1, len(liste)):
                numbers.append(liste[x][1] + numbers[x - 1])

            #take one them from the list (randomly)
            mot = random.randint(0, numbers[len(numbers) - 1])
            for x in xrange(0, len(numbers)):
                if mot <= numbers[x]:
                    mot = liste[x][0]
                    break

            #if the word is already choosen, pick the next one
            while mot in sentence:
                x += 1
                if x >= len(liste) - 1:
                    mot = ''
                    break
                mot = liste[x][0]

            mot = mot.split(" ")
            mot.reverse()
            if mot == ['']:
                done = 1
            else:
                #map((lambda x: sentence.insert(0, x)), mot)
                [sentence.insert(0, x) for x in mot]

        pre_words = sentence
        sentence = sentence[-2:]

        # Now build sentence forwards from "chosen" word

        #We've got
        #cwords:    ...    cwords[w-1]    cwords[w]    cwords[w+1]    cwords[w+2]
        #sentence:    ...    sentence[-2]    sentence[-1]    look_for    look_for ?

        #we are looking, for a cwords[w] known, and maybe a cwords[w-1] known, what will be the cwords[w+1] to choose.
        #cwords[w+2] is need when cwords[w+1] is in ignored list


        done = 0
        while done == 0:
            #create a dictionary wich will contain all the words we can found before the "chosen" word
            post_words = {"" : 0}
            word = str(sentence[-1].split(" ")[-1])
            for x in self.words[word]:
                if len(x) == 10:
                    l, w = struct.unpack("qH", x)
                else:
                    l, w = struct.unpack("lH", x)
                context = self.lines[l][0]
                num_context = self.lines[l][1]
                cwords = context.split()
                #look if we can found a pair with the choosen word, and the next one
                if len(sentence) > 1:
                    if sentence[len(sentence) - 2] != cwords[w - 1]:
                        continue

                if w < len(cwords) - 1:
                    #if the word is in ignore_list, look the next word
                    look_for = cwords[w + 1]
                    if look_for in self.settings.ignore_list and w < len(cwords) - 2:
                        look_for = look_for + " " + cwords[w + 2]

                    if not(post_words.has_key(look_for)):
                        post_words[look_for] = num_context
                    else :
                        post_words[look_for] += num_context
                else:
                    post_words[""] += num_context
            #Sort the words
            liste = post_words.items()
            liste.sort(lambda x, y: cmp(y[1], x[1]))
            numbers = [liste[0][1]]

            for x in xrange(1, len(liste)):
                numbers.append(liste[x][1] + numbers[x - 1])

            #take one them from the list (randomly)
            mot = random.randint(0, numbers[len(numbers) - 1])
            for x in xrange(0, len(numbers)):
                if mot <= numbers[x]:
                    mot = liste[x][0]
                    break

            x = -1
            while mot in sentence:
                x += 1
                if x >= len(liste) - 1:
                    mot = ''
                    break
                mot = liste[x][0]


            mot = mot.split(" ")
            if mot == ['']:
                done = 1
            else:
                [ sentence.append(x) for x in mot]
                #map((lambda x: sentence.append(x)), mot)

        sentence = pre_words[:-2] + sentence

        #Replace aliases
        for x in xrange(0, len(sentence)):
            if sentence[x][0] == "~":
                sentence[x] = sentence[x][1:]

        #Insert space between each words
        #map((lambda x: sentence.insert(1 + x * 2, " ")), xrange(0, len(sentence) - 1))
        [sentence.insert(1 + x * 2, " ") for x in xrange(0, len(sentence) - 1)]

        #correct the ' & , spaces problem
        #code is not very good and can be improve but does his job...
        for x in xrange(0, len(sentence)):
            if sentence[x] == "'":
                sentence[x - 1] = ""
                if x + 1 < len(sentence):
                    sentence[x + 1] = ""
            for split_char in ['?', '!', ',']:
                if sentence[x] == split_char:
                    sentence[x - 1] = ""

        #return as string..
        return "".join(sentence)

    def learn(self, body, num_context = 1):
        """
        Lines should be cleaned (filter_message()) before passing
        to this.
        """

        def learn_line(self, body, num_context):
            """
            Learn from a sentence.
            """

            words = body.split()
            # Ignore sentences of < 1 words XXX was < 3
            if len(words) < 1:
                return

            #voyelles = u"aÃ Ã¢eÃ©Ã¨ÃªiÃ®Ã¯oÃ¶Ã´uÃ¼Ã»yaAeEiIoOuUyY"
            for x in xrange(0, len(words)):

                #nb_voy = 0
                digit = 0
                char = 0

                for c in words[x]:
                    #print "Checking for %r (%s) in %s (%s)" % (c, type(c), voyelles, type(voyelles))
                    #if c in voyelles:
                    #    nb_voy += 1
                    if c.isalpha():
                        char += 1
                    if c.isdigit():
                        digit += 1

                for censored in self.settings.censored:
                    pattern = "^%s$" % censored
                    if re.search(pattern, words[x]):
                        print "Censored word %s" % words[x]
                        return

                #or (((nb_voy * 100) / len(words[x]) < 21) and len(words[x]) > 5) \
                if len(words[x]) > 13 \
                or (char and digit) \
                or (self.words.has_key(words[x]) == 0 and self.settings.learning == 0):
                    #if one word as more than 13 characters, don't learn
                    #        (in french, this represent 12% of the words)
                    #and don't learn words where there are less than 20% of voyels
                    #don't learn the sentence if one word is censored
                    #don't learn too if there are digits and char in the word
                    #same if learning is off
                    return
                #elif ("-" in words[x] or "_" in words[x]) :
                #    words[x] = "#nick"


            num_w = self.settings.num_words
            if num_w != 0:
                num_cpw = self.settings.num_contexts / float(num_w) # contexts per word
            else:
                num_cpw = 0

            cleanbody = " ".join(words)

            # Hash collisions we don't care about. 2^32 is big :-)
            hashval = hash(cleanbody)

            # Check context isn't already known
            if not self.lines.has_key(hashval):
                if not(num_cpw > 100 and self.settings.learning == 0):

                    self.lines[hashval] = [cleanbody, num_context]
                    # Add link for each word
                    for x in xrange(0, len(words)):
                        if self.words.has_key(words[x]):
                            # Add entry. (line number, word number)
                            self.words[words[x]].append(struct.pack("qH", hashval, x))
                        else:
                            self.words[words[x]] = [ struct.pack("qH", hashval, x) ]
                            self.settings.num_words += 1
                        self.settings.num_contexts += 1
            else :
                self.lines[hashval][1] += num_context

            #is max_words reached, don't learn more
            if self.settings.num_words >= self.settings.max_words:
                print "Not learning new words because %s >= %s" % (self.settings.num_words, self.settings.max_words)
                self.settings.learning = 0

        # Split body text into sentences and parse them
        # one by one.
        body += " "
        #map ((lambda x : learn_line(self, x, num_context)), body.split(". "))
        [learn_line(self, x, num_context) for x in body.split(". ")]
