#! /usr/bin/env python
# vim: set sw=4 sts=4 ts=8 et:
#
# PyBorg IRC module
#
# Copyright (c) 2000, 2006 Tom Morton, Sebastien Dailly
#
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

import sys, time
from threading import Timer

try:
    print(sys.path)
    import discord
except:
    print "ERROR !!!!\discord.py not found, please install it\n"
    sys.exit(1)

#overide irclib function

import os
import pyborg
import discord
import cfgfile
import random
import time
import traceback
import thread
from pprint import pprint

def get_time():
    """
    Return time as a nice yummy string
    """
    return time.strftime("%H:%M:%S", time.localtime(time.time()))


#class ModIRC(SingleServerIRCBot):
class DiscordBot(object):
    """
    Module to interface discord input and output with the PyBorg learn
    and reply modules.
    """
    # The bot recieves a standard message on join. The standard part
    # message is only used if the user doesn't have a part message.
    join_msg = "%s"# is here"
    part_msg = "%s"# has left"

    # For security the owner's host mask is stored
    # DON'T CHANGE THIS
    owner_mask = []


    # Command list for this module
    commandlist =   "IRC Module Commands:\n!chans, !ignore, \
!join, !nick, !part, !quit, !quitmsg, !jump, !reply2ignored, !replyrate, !shutup, \
!stealth, !unignore, !wakeup, !talk, !me, !owner"
    # Detailed command description dictionary
    commanddict = {
            "shutup": "Owner command. Usage: !shutup\nStop the bot talking",
            "wakeup": "Owner command. Usage: !wakeup\nAllow the bot to talk",
            "join": "Owner command. Usage: !join #chan1 [#chan2 [...]]\nJoin one or more channels",
            "part": "Owner command. Usage: !part #chan1 [#chan2 [...]]\nLeave one or more channels",
            "chans": "Owner command. Usage: !chans\nList channels currently on",
            "nick": "Owner command. Usage: !nick nickname\nChange nickname",
            "ignore": "Owner command. Usage: !ignore [nick1 [nick2 [...]]]\nIgnore one or more nicknames. Without arguments it lists ignored nicknames",
            "unignore": "Owner command. Usage: !unignore nick1 [nick2 [...]]\nUnignores one or more nicknames",
            "replyrate": "Owner command. Usage: !replyrate [rate%]\nSet rate of bot replies to rate%. Without arguments (not an owner-only command) shows the current reply rate",
            "reply2ignored": "Owner command. Usage: !reply2ignored [on|off]\nAllow/disallow replying to ignored users. Without arguments shows the current setting",
            "stealth": "Owner command. Usage: !stealth [on|off]\nTurn stealth mode on or off (disable non-owner commands and don't return CTCP VERSION). Without arguments shows the current setting",
            "quitmsg": "Owner command. Usage: !quitmsg [message]\nSet the quit message. Without arguments show the current quit message",
            "talk": "Owner command. Usage !talk nick message\nmake the bot send the sentence 'message' to 'nick'",
            "me": "Owner command. Usage !me nick message\nmake the bot send the sentence 'message' to 'nick'",
            "jump": "Owner command. Usage: !jump\nMake the bot reconnect to IRC",
            "quit": "Owner command. Usage: !quit\nMake the bot quit IRC",
            "owner": "Usage: !owner password\nAllow to become owner of the bot"
    }

    def __init__(self, my_pyborg, args):
        """
        Args will be sys.argv (command prompt arguments)
        """
        # PyBorg
        self.pyborg = my_pyborg
        # load settings

        self.settings = cfgfile.cfgset()
        self.settings.load("pyborg-discord.cfg",
                { "myname": ("The bot's nickname", "PyBorg"),
                  #"realname": ("Reported 'real name'", "Pyborg"),
                  #"localaddress": ("Local IP to bind to", ""),
                  #"ipv6": ("Whether to use IPv6", 0),
                  "owners": ("Owner(s) nickname", [ "OwnerNick" ]),
                  #"servers": ("Discord Server to pay attention to (server name)", [("irc.sucks.net")]),
                  #"chans": ("Channels to pay attention to", ["#cutie578"]),
                  'attentive_channels' : ("Server/channel combos to pay attention to", {}),
                  "speaking": ("Allow the bot to talk on channels", 1),
                  "stealth": ("Hide the fact we are a bot", 0),
                  "ignorelist": ("Ignore these nicknames:", []),
                  "reply2ignored": ("Reply to ignored people", 0),
                  "reply_chance": ("Chance of reply (%) per message", 10),
                  "quitmsg": ("IRC quit message", "Bye :-("),
                  #"password": ("password for control the bot (Edit manually !)", ""),
                  "autosaveperiod": ("Save every X minutes. Leave at 0 for no saving.", 60),
                  "disco_auto": ("username and password for discord", ("", "")),
                  "magic_words" : ("magic notification words", [])
                })

        # If autosaveperiod is set, trigger it.
        asp = self.settings.autosaveperiod
        if(asp > 0) :
            self.autosave_schedule(asp)

        # Create useful variables.
        self.owners = self.settings.owners[:]
        #self.chans = self.settings.chans[:]
        self.inchans = []
        self.wanted_myname = self.settings.myname
        self.attempting_regain = False
        self.feature_monitor = False
        self.client = discord.Client()

        # Parse command prompt parameters

        #for x in xrange(1, len(args)):
        #    # Specify servers
        #    if args[x] == "-s":
        #        self.settings.servers = []
        #        # Read list of servers
        #        for y in xrange(x+1, len(args)):
        #            if args[y][0] == "-":
        #                break
        #            server = args[y].split(":")
        #            # Default port if none specified
        #            if len(server) == 1:
        #                server.append("6667")
        #            self.settings.servers.append((server[0], int(server[1])))
        #    # Channels
        #    if args[x] == "-c":
        #        self.settings.chans = []
        #        # Read list of channels
        #        for y in xrange(x+1, len(args)):
        #            if args[y][0] == "-":
        #                break
        #            self.settings.chans.append("#"+args[y])
        #    # Nickname
        #    if args[x] == "-n":
        #        try:
        #            self.settings.myname = args[x+1]
        #        except IndexError:
        #            pass

    def our_start(self):
        print "Connecting to server..."
        #SingleServerIRCBot.__init__(self, self.settings.servers, self.settings.myname, self.settings.realname, 2, self.settings.localaddress, self.settings.ipv6)
        try:
            self.client.login(self.settings.disco_auth[0], self.settings.disco_auth[1])
        except Exception, e:
            print "Could not authenticate to discord"
            raise e

        #self.connection.execute_delayed(20, self._chan_checker)
        #self.connection.execute_delayed(20, self._nick_checker)
        #self.start()


        @self.client.event
        def on_ready():
            print('Logged in as')
            print(self.client.user.name)
            print(self.client.user.id)
            print('------')


        @self.client.event
        def on_message(message):
            """
            Process messages.
            """

            #Ensure we actually want to hook onto this message
            if message.server.name in self.settings.attentive_channels and message.channel.name in self.settings.attentive_channels[message.server.name].keys():
                pass
            else:
                return

            source = message.author.name
            target = message.channel.name
            channel_settings = self.settings.attentive_channels[message.server.name][message.channel.name]

            learn = 1

            # First message from owner 'locks' the owner host mask
            # se people can't change to the owner nick and do horrible
            # stuff like '!unlearn the' :-)
            if not source in self.owner_mask and source in self.owners:
                self.owner_mask.append(source)
                print "Locked owner as %s" % source

            body = message.content

            # WHOOHOOO!!
            if target == self.settings.myname or source == self.settings.myname:
                print "[%s] <%s> > %s> %s" % (get_time(), source, target, body)

            # Ignore self.
            if source == self.client.user.name: return

            body_contains_me = body.lower().find(self.client.user.name.lower()) != -1
            print body

            # We want replies reply_chance%, if speaking is on
            if channel_settings.get('read_only', True) or self.settings.speaking == 0:
                replyrate = 0
            else:
                replyrate = channel_settings.get("reply_chance", self.settings.reply_chance)

                if body_contains_me:
                    body = body.lower().replace(self.client.user.name.lower(), '')
                    replyrate = channel_settings.get('notice_chance', replyrate)
                    #replyrate = 100

                #check for magic word lists
                if len(self.settings.magic_words) > 0:
                    if channel_settings.get('magic_chance', 0) > replyrate:
                        for magic in self.settings.magic_words:
                            if magic.lower() in body.lower():
                                replyrate = channel_settings.get('magic_chance', replyrate)
                                break

            # Ignore selected nicks
            if self.settings.ignorelist.count(source.lower()) > 0 \
                    and self.settings.reply2ignored == 1:
                print "Nolearn from %s" % source
                learn = 0
            elif self.settings.ignorelist.count(source.lower()) > 0:
                print "Ignoring %s" % source
                return
            elif len(body.split(" ")) <= 3:
                #Short phrases aren't enough to learn from
                learn = 0

            # Stealth mode. disable commands for non owners
            if (not source in self.owners) and self.settings.stealth:
                while body[:1] == "!":
                    body = body[1:]

            if body == "":
                return

            # Pass message onto pyborg
            if source in self.owners: #and e.source() in self.owner_mask:
                #self.pyborg.process_msg(self, body, replyrate, learn, (body, source, target, c, e), owner=1)
                self.pyborg.process_msg(self, body, replyrate, learn, (body, message.channel, 'public'), owner=1)
            else:
                #start a new thread
                #thread.start_new_thread(self.pyborg.process_msg, (self, body, replyrate, learn, (body, message.channel, 'public')))
                self.pyborg.process_msg(self, body, replyrate, learn, (body, message.channel, 'public'))
                pass

    #def on_msg(self, c, e):
        self.client.run()


    #def on_welcome(self, c, e):
    #    print self.chans
    #    if self.settings.nickserv and self.settings.nickserv[0] != '':
    #        if len(self.settings.nickserv) == 2 and self.settings.nickserv[1] != '':
    #            c.privmsg('NickServ', 'identify ' + self.settings.nickserv[0] + ' ' + self.settings.nickserv[1])
    #        else:
    #            c.privmsg('NickServ', 'identify ' + self.settings.nickserv)
    #    for i in self.chans:
    #        c.join(i)

    #def shutdown(self):
    #    try:
    #        self.die() # disconnect from server
    #    except AttributeError, e:
    #        # already disconnected probably (pingout or whatever)
    #        pass

    #def get_version(self):
    #    if self.settings.stealth:
    #        # stealth mode. we shall be a windows luser today
    #        return "VERSION mIRC32 v5.6 K.Mardam-Bey"
    #    else:
    #        return self.pyborg.ver_string

    #def on_kick(self, c, e):
    #    """
    #    Process leaving
    #    """
    #    # Parse Nickname!username@host.mask.net to Nickname
    #    kicked = e.arguments()[0]
    #    kicker = e.source().split("!")[0]
    #    target = e.target() #channel
    #    if len(e.arguments()) >= 2:
    #        reason = e.arguments()[1]
    #    else:
    #        reason = ""

    #    if kicked == self.settings.myname:
    #        print "[%s] <--  %s was kicked off %s by %s (%s)" % (get_time(), kicked, target, kicker, reason)
    #        self.inchans.remove(target.lower())

    #def on_part(self, c, e):
    #    """
    #    Process leaving
    #    """
    #    # Parse Nickname!username@host.mask.net to Nickname
    #    parter = e.source().split("!")[0]

    #    if parter == self.settings.myname:
    #        target = e.target() #channel
    #        self.inchans.remove(target.lower())

    #def on_join(self, c, e):
    #    """
    #    Process Joining
    #    """
    #    # Parse Nickname!username@host.mask.net to Nickname
    #    joiner = e.source().split("!")[0]

    #    if joiner == self.settings.myname:
    #        target = e.target() #channel
    #        self.inchans.append(target.lower())

    #def on_privmsg(self, c, e):
    #    self.on_msg(c, e)

    #def on_featurelist(self, c, e):
    #    for feature in e.arguments():
    #        if feature[:8] == "MONITOR=":
    #            print "MONITOR supported."
    #            self.feature_monitor = True
    #            c.send_raw("MONITOR + %s" % self.wanted_myname)
    #            break

    #def _failed_new_nickname(self, c, e):
    #    if self.attempting_regain is False:
    #        self.settings.myname = c.get_nickname()[:8] + `random.randint(0, 9)`
    #        self.connection.nick(self.settings.myname)
    #    else:
    #        if self.feature_monitor:
    #            # A collision may have occurred, check again.
    #            c.send_raw("MONITOR s")
    #        self.settings.myname = c.get_nickname()
    #        self.attempting_regain = False

    #def on_nicknameinuse(self, c, e):
    #    self._failed_new_nickname(c, e)

    #def on_erroneusnickname(self, c, e):
    #    self._failed_new_nickname( c, e)

#   # def on_unavailresource(self, c, e):
#   #     self._failed_new_nickname(c, e)

    #def on_pubmsg(self, c, e):
    #    self.on_msg(c, e)

    #def on_ctcp(self, c, e):
    #    ctcptype = e.arguments()[0]
    #    if ctcptype == "ACTION":
    #        self.on_msg(c, e)
    #    else:
    #        SingleServerIRCBot.on_ctcp(self, c, e)

    def disconnect(self):
        print "deconnection"
        self.attempting_regain = False
        self.feature_monitor = False
        self.client.logout()


    #def irc_commands(self, body, source, target, c, e):
    #    """
    #    Special IRC commands.
    #    """
    #    msg = ""

    #    command_list = body.split()
    #    command_list[0] = command_list[0].lower()

    #    ### User commands
    #    # Query replyrate
    #    if command_list[0] == "!replyrate" and len(command_list)==1:
    #        msg = "Reply rate is "+`self.settings.reply_chance`+"%."

    #    if command_list[0] == "!owner" and len(command_list) > 1 and source not in self.owners:
    #        if command_list[1] == self.settings.password:
    #            self.owners.append(source)
    #            self.output("You've been added to owners list", ("", source, target, c, e))
    #        else:
    #            self.output("Try again", ("", source, target, c, e))

    #    ### Owner commands
    #    if source in self.owners and e.source() in self.owner_mask:

    #        # Change nick
    #        if command_list[0] == "!nick":
    #            try:
    #                self.connection.nick(command_list[1])
    #                self.settings.myname = command_list[1]
    #                self.wanted_myname = self.settings.myname
    #            except:
    #                pass
    #        # stealth mode
    #        elif command_list[0] == "!stealth":
    #            msg = "Stealth mode "
    #            if len(command_list) == 1:
    #                if self.settings.stealth == 0:
    #                    msg = msg + "off"
    #                else:
    #                    msg = msg + "on"
    #            else:
    #                toggle = command_list[1].lower()
    #                if toggle == "on":
    #                    msg = msg + "on"
    #                    self.settings.stealth = 1
    #                else:
    #                    msg = msg + "off"
    #                    self.settings.stealth = 0

    #        # filter mirc colours out?
    #        elif command_list[0] == "!nocolor" or command_list[0] == "!nocolour":
    #            msg = "obsolete command "

    #        # Allow/disallow replying to ignored nicks
    #        # (they will never be learnt from)
    #        elif command_list[0] == "!reply2ignored":
    #            msg = "Replying to ignored users "
    #            if len(command_list) == 1:
    #                if self.settings.reply2ignored == 0:
    #                    msg = msg + "off"
    #                else:
    #                    msg = msg + "on"
    #            else:
    #                toggle = command_list[1]
    #                if toggle == "on":
    #                    msg = msg + "on"
    #                    self.settings.reply2ignored = 1
    #                else:
    #                    msg = msg + "off"
    #                    self.settings.reply2ignored = 0
    #        # Stop talking
    #        elif command_list[0] == "!shutup":
    #            if self.settings.speaking == 1:
    #                msg = "I'll be quiet :-("
    #                self.settings.speaking = 0
    #            else:
    #                msg = ":-x"
    #        # Wake up again
    #        elif command_list[0] == "!wakeup":
    #            if self.settings.speaking == 0:
    #                self.settings.speaking = 1
    #                msg = "Whoohoo!"
    #            else:
    #                msg = "But i'm already awake..."

    #        # Join a channel or list of channels
    #        elif command_list[0] == "!join":
    #            for x in xrange(1, len(command_list)):
    #                if not command_list[x] in self.chans:
    #                    self.chans.append(command_list[x])
    #                if not command_list[x].lower() in self.inchans:
    #                    msg = "Attempting to join channel %s" % command_list[x]
    #                    c.join(command_list[x])

    #        # Part a channel or list of channels
    #        elif command_list[0] == "!part":
    #            for x in xrange(1, len(command_list)):
    #                if command_list[x] in self.chans:
    #                    self.chans.remove(command_list[x])
    #                if command_list[x].lower() in self.inchans:
    #                    msg = "Leaving channel %s" % command_list[x]
    #                    c.part(command_list[x])

    #        # List channels currently on
    #        elif command_list[0] == "!chans":
    #            if len(self.channels.keys())==0:
    #                msg = "I'm currently on no channels"
    #            else:
    #                msg = "I'm currently on "
    #                channels = self.channels.keys()
    #                for x in xrange(0, len(channels)):
    #                    msg = msg+channels[x]+" "
    #        # add someone to the ignore list
    #        elif command_list[0] == "!ignore":
    #            # if no arguments are given say who we are
    #            # ignoring
    #            if len(command_list) == 1:
    #                msg = "I'm ignoring "
    #                if len(self.settings.ignorelist) == 0:
    #                    msg = msg + "nobody"
    #                else:
    #                    for x in xrange(0, len(self.settings.ignorelist)):
    #                        msg = msg + self.settings.ignorelist[x] + " "
    #            # Add everyone listed to the ignore list
    #            # eg !ignore tom dick harry
    #            else:
    #                for x in xrange(1, len(command_list)):
    #                    self.settings.ignorelist.append(command_list[x].lower())
    #                    msg = "done"
    #        # remove someone from the ignore list
    #        elif command_list[0] == "!unignore":
    #            # Remove everyone listed from the ignore list
    #            # eg !unignore tom dick harry
    #            for x in xrange(1, len(command_list)):
    #                try:
    #                    self.settings.ignorelist.remove(command_list[x].lower())
    #                    msg = "done"
    #                except:
    #                    pass
    #        # set the quit message
    #        elif command_list[0] == "!quitmsg":
    #            if len(command_list) > 1:
    #                self.settings.quitmsg = body.split(" ", 1)[1]
    #                msg = "New quit message is \"%s\"" % self.settings.quitmsg
    #            else:
    #                msg = "Quit message is \"%s\"" % self.settings.quitmsg
    #        # make the pyborg quit
    #        elif command_list[0] == "!quit":
    #            sys.exit()
    #        elif command_list[0] == "!jump":
    #            print("Jumping servers...")
    #            self.jump_server()
    #        # Change reply rate
    #        elif command_list[0] == "!replyrate":
    #            try:
    #                self.settings.reply_chance = int(command_list[1])
    #                msg = "Now replying to %d%% of messages." % int(command_list[1])
    #            except:
    #                msg = "Reply rate is %d%%." % self.settings.reply_chance
    #        #make the bot talk
    #        elif command_list[0] == "!talk":
    #            if len(command_list) >= 2:
    #                phrase=""
    #                for x in xrange (2, len (command_list)):
    #                    phrase = phrase + str(command_list[x]) + " "
    #                self.output(phrase, ("", command_list[1], "", c, e))
    #        #make the bot /me
    #        elif command_list[0] == "!me":
    #            if len(command_list) >= 2:
    #                phrase=""
    #                for x in xrange (2, len (command_list)):
    #                    phrase = phrase + str(command_list[x]) + " "
    #                self.output("\x01ACTION " + phrase + "\x01", ("", command_list[1], "", c, e))
    #        # Save changes
    #        save_myname = self.settings.myname
    #        if self.wanted_myname is not None:
    #            self.settings.myname = self.wanted_myname
    #        self.pyborg.settings.save()
    #        self.settings.save()
    #        self.settings.myname = save_myname

    #    if msg == "":
    #        return 0
    #    else:
    #        self.output(msg, ("<none>", source, target, c, e))
    #        return 1


    #def _chan_checker(self):
    #    if self.connection.is_connected():
    #        for i in self.chans:
    #            if not i.split()[0].lower() in self.inchans:
    #                print "Attempting to rejoin %s" % i
    #                self.connection.join(i)
    #    self.connection.execute_delayed(20, self._chan_checker)

    #def _nick_checker(self):
    #    if (self.connection.is_connected() and
    #        self.feature_monitor is False and
    #        self.connection.get_nickname() != self.wanted_myname):
    #           self.connection.ison([self.wanted_myname])
    #    self.connection.execute_delayed(20, self._nick_checker)

    #def _try_regain(self, nick):
    #        print "Attempting to regain nickname %s" % nick
    #        self.attempting_regain = True
    #        self.settings.myname = nick
    #        self.connection.nick(self.settings.myname)

    #def on_ison(self, c, e):
    #    nick_found = False
    #    for nick in e.arguments()[0].split():
    #        if nick.lower() == self.wanted_myname.lower():
    #            nick_found = True
    #            break
    #    if not nick_found:
    #        self._try_regain(self.wanted_myname)

    #def on_monoffline(self, c, e):
    #    for nick in e.arguments()[0].split(','):
    #        if nick.lower() == self.wanted_myname.lower():
    #            self._try_regain(self.wanted_myname)
    #            break

    def output(self, message, args):
        """
        Output a line of text.
        old argss = (body, source, target, c, e)
        new args = (body, target, msg_type)
        """
        print "Calling output"
        #if not self.connection.is_connected():
        if not self.client.is_logged_in:
            print "Can't send reply : not connected to server"
            return

        # Unwrap arguments
        #print "Attempting to parse passed args:"
        #print(args)
        body, target, msg_type = args

        # Decide. should we do a ctcp action?
        # TODO: Figure out if this is passed in anywhere
        action = 0
        #if message.find(self.settings.myname.lower()+" ") == 0:
        #    action = 1
        #    message = message[len(self.settings.myname)+1:]
        #else:
        #    action = 0

        # Joins replies and public messages
        if msg_type == "public":

            self.client.send_typing(target)
            time.sleep(.06 * len(message.split(" ")))

            if action == 0:
                self.client.send_message(target, message)
            else:
                self.client.send_message(target, "/me" + message)
        # Private messages
        elif msg_type == "priv":
            # normal private msg
            pass
            #if action == 0:
            #    print "[%s] <%s> > %s> %s" % (get_time(), self.settings.myname, source, message)
            #    c.privmsg(source, message)
            #    # send copy to owner
            #    if not source in self.owners:
            #        c.privmsg(','.join(self.owners), "(From "+source+") "+body)
            #        c.privmsg(','.join(self.owners), "(To   "+source+") "+message)
            ## ctcp action priv msg
            #else:
            #    print "[%s] <%s> > %s> /me %s" % (get_time(), self.settings.myname, target, message)
            #    c.action(source, message)
            #    # send copy to owner
            #    if not source in self.owners:
            #        map ((lambda x: c.action(x, "(From "+source+") "+body)), self.owners)
            #        map ((lambda x: c.action(x, "(To   "+source+") "+message)), self.owners)

    ##
    # This function schedules autosave_execute to happen every asp minutes
    # @param asp the autosave period, configured on pyborg-irc.cfg, in minutes.
    def autosave_schedule(self, asp) :
        timer = Timer(asp * 60, self.autosave_execute, ())
        self.should_autosave = True
        timer.setDaemon(True)
        timer.start()

    ##
    # This function gets called every autosaveperiod minutes, and executes the autosaving.
    # @param asp autosaveperiod, see above.
    def autosave_execute(self) :
        if self.should_autosave:
            self.pyborg.save_all()
            self.autosave_schedule(self.settings.autosaveperiod)

    def autosave_stop(self):
        self.should_autosave = False

if __name__ == "__main__":

    if "--help" in sys.argv:
        print "Pyborg discord bot. Usage:"
        print " pyborg-discord.py [options]"
        print " -s   server:port"
        print " -c   channel"
        print " -n   nickname"
        print "Defaults stored in pyborg-discord.cfg"
        print
        sys.exit(0)
    # start the pyborg
    my_pyborg = pyborg.pyborg()
    #bot = ModIRC(my_pyborg, sys.argv)
    bot = DiscordBot(my_pyborg, sys.argv)
    try:
        bot.our_start()
    except KeyboardInterrupt, e:
        pass
    except SystemExit, e:
        pass
    except:
        traceback.print_exc()
        c = raw_input("Ooops! It looks like Pyborg has crashed. Would you like to save its dictionary? (y/n) ")
        if c.lower()[:1] == 'n':
            sys.exit(0)
    bot.autosave_stop()
    #bot.disconnect(bot.settings.quitmsg)
    bot.disconnect()
    if my_pyborg.saving:
        while my_pyborg.saving:
            print "Waiting for save in other thread..."
            time.sleep(1)
    else:
        my_pyborg.save_all()
    del my_pyborg
