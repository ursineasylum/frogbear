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
    import discord
except Exception, e:
    print str(e)
    print "ERROR !!!!\discord.py not found, please install it\n"
    sys.exit(1)

#overide irclib function

import os, re
import pyborg
import discord
import cfgfile
import random
import time
import traceback
import thread
import logging
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
        self.settings.load("pyborg-discord.json",
                { "myname": ("The bot's nickname", "PyBorg"),
                  "owners": ("Owner(s) nickname", []),
                  "interaction_settings" : ("Server/channel combos to pay attention to", {}),
                  "interaction_defaults" : ("Server/channel global settings, for when replacements aren't set.", {}),
                  "interaction_private" : ("Settings for private message replies.", {}),
                  "speaking": ("Allow the bot to talk on channels", 1),
                  "stealth": ("Hide the fact we are a bot", 0),
                  "ignorelist": ("Ignore these nicknames:", []),
                  "reply2ignored": ("Reply to ignored people", 0),
                  "quitmsg": ("IRC quit message", "Bye :-("),
                  "autosaveperiod": ("Save every X minutes. Leave at 0 for no saving.", 60),
                  "magic_words" : ("magic notification words", []),
                  "disco_auth" : ("Discord authentication creds", [])
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
        self.pyborg.bot_name = self.settings.myname
        self.attempting_regain = False
        self.feature_monitor = False
        self.client = discord.Client()

        self.roles = {}
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
        #SingleServerIRCBot.__init__(self, self.settings.servers, self.settings.myname, self.settings.realname, 2, self.settings.localaddress, self.settings.ipv6)
        try:
            self.client.login(self.settings.disco_auth[0], self.settings.disco_auth[1])
        except Exception, e:
            print "Could not authenticate to discord: %s" % str(e)
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

            print "Getting a server list"
            servers = self.client.servers
            print servers
            for server in servers:
                print "Checking for %s in %s" % (server.name, self.settings.interaction_settings.keys())
                if server.name in self.settings.interaction_settings.keys():
                    self.roles[server.name] = {x.name : x for x in server.roles}



        @self.client.event
        def on_message(message):
            """
            Process messages.
            """
            #Ensure we actually want to hook onto this message
            is_private = False
            source = message.author.name
            target = message.channel
            if hasattr(message.channel, 'is_private') and message.channel.is_private:
                #It's a private message.
                is_private = True
                channel_settings = self.settings.interaction_private
            elif message.server.name in self.settings.interaction_settings and message.channel.name in self.settings.interaction_settings[message.server.name].keys():
                channel_settings = self.settings.interaction_settings[message.server.name][message.channel.name]
                for def_set in self.settings.interaction_defaults.keys():
                    if def_set not in channel_settings:
                        channel_settings[def_set] = self.settings.interaction_defaults[def_set]
            else:
                return


            learn = channel_settings['learning']

            # First message from owner 'locks' the owner host mask
            # se people can't change to the owner nick and do horrible
            # stuff like '!unlearn the' :-)
            if not source in self.owner_mask and source in self.owners:
                self.owner_mask.append(source)
                print "Locked owner as %s" % source

            body = message.content
            if len(message.mentions) > 0:
                body = re.sub("<@\d+>", "%s", message.content) % tuple([x.name for x in message.mentions])

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
                replyrate = channel_settings.get("reply_chance", 0)

                if body_contains_me:
                    #body = body.lower().replace(self.client.user.name.lower(), '')
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
                learn = False
            elif self.settings.ignorelist.count(source.lower()) > 0:
                print "Ignoring %s" % source
                return
            elif len(body.split(" ")) <= 3:
                #Short phrases aren't enough to learn from
                learn = False

            # Stealth mode. disable commands for non owners
            if (not source in self.owners) and not channel_settings['command_response']:
                while body[:1] == "!":
                    body = body[1:]

            if body == "":
                return

            # Pass message onto pyborg
            channel_type = "public"
            if is_private:
                channel_type = "private"

            if source in self.owners:
                owner = True
            else:
                owner = False

            cmd_resp = channel_settings['command_response']
            ctxt_resp = channel_settings['context_response']
            opsec_level = channel_settings['opsec_level']

            self.pyborg.process_msg(self, body, replyrate, learn, (body, source, target, channel_type), owner=owner, cmd_resp=cmd_resp, ctxt_resp=ctxt_resp, opsec_level=opsec_level)

            #if source in self.owners: #and e.source() in self.owner_mask:
            #    #self.pyborg.process_msg(self, body, replyrate, learn, (body, source, target, c, e), owner=1)
            #    self.pyborg.process_msg(self, body, replyrate, learn, (body, message.channel, channel_type), owner=1)
            #else:
            #    #start a new thread
            #    #thread.start_new_thread(self.pyborg.process_msg, (self, body, replyrate, learn, (body, message.channel, 'public')))
            #    self.pyborg.process_msg(self, body, replyrate, learn, (body, message.channel, 'public'))
            #    pass

        self.client.run()



    def disconnect(self):
        print "Disconnecting."
        self.attempting_regain = False
        self.feature_monitor = False
        try:
            self.client.logout()
        except AttributeError, e:
            print "Error logging out."

    def set_role(self, role, target, args):
        """
        Force-set a role of a target
        """
        body, source, raw_target, msg_type = args

        if isinstance(target, basestring):
            member_list = {c.name : c for c in self.client.get_all_members()}

            if target in member_list:
                target = member_list[target]

            else:
                print "Could not find target member %s" % target
                return

        if isinstance(role, basestring):
            if role in self.roles[target.server.name].keys():
                role = self.roles[target.server.name][role]
            else:
                print "Could not find role %s on target server %s" % (role, target.server.name)
                return

        target_roles = target.roles
        target_roles.append(role)


        self.client.add_roles(target, *target_roles)


    def kick(self, message, args):
        """
        Discord-kick a member target with a message
        """
        body, source, target, msg_type = args


        if isinstance(source, basestring):
            source_list = {c.name : c for c in self.client.get_all_members()}

            if source in source_list:
                source = source_list[source]

            else:
                print "Could not find target source %s" % target
                return

        self.output(message, args)
        self.client.kick(target.server, source)

    def output(self, message, args):
        """
        Output a line of text.
        old argss = (body, source, target, c, e)
        new args = (body, source, target, msg_type)
        """
        print "Calling output"
        #if not self.connection.is_connected():
        if not self.client.is_logged_in:
            print "Can't send reply : not connected to server"
            return

        # Unwrap arguments
        print "Attempting to parse passed args:"
        #print(args)
        #pprint(args)
        body, source, target, msg_type = args


        if isinstance(target, basestring):
            if msg_type == "public":
                channel_list = {c.name : c for c in self.client.get_all_channels()}
            else:
                channel_list = {c.name : c for c in self.client.get_all_members()}

            if target in channel_list:
                target = channel_list[target]

            else:
                print "Could not find target channel %s" % target
                return

        # Decide. should we do a ctcp action?
        # TODO: Figure out if this is passed in anywhere
        action = 0
        #if message.find(self.settings.myname.lower()+" ") == 0:
        #    action = 1
        #    message = message[len(self.settings.myname)+1:]
        #else:
        #    action = 0

        # Joins replies and public messages
        if isinstance(message, unicode):
            message = message.encode("utf-8")

        if msg_type == "public":

            self.client.send_typing(target)
            time.sleep(.06 * len(message.split(" ")))

            if action == 0:
                self.client.send_message(target, message)
            else:
                self.client.send_message(target, "/me" + message)
        # Private messages
        elif msg_type == "private":
            self.client.send_message(target, message)
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
    run = True
    wait = 0
    while(run):
        time.sleep(wait)
        my_pyborg = pyborg.pyborg()
        #bot = ModIRC(my_pyborg, sys.argv)
        bot = DiscordBot(my_pyborg, sys.argv)
        try:
            wait = 0
            bot.our_start()
        except KeyboardInterrupt, e:
            run = False
        except SystemExit, e:
            pass
            #run = False
        except:
            traceback.print_exc()
            #c = raw_input("Ooops! It looks like Pyborg has crashed.")
            print "Pyborg crash, restarting in 10 seconds."
            wait = 10
            #if c.lower()[:1] == 'n':
            #    sys.exit(0)
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
