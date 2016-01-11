# -*- coding: utf-8 -*-
# vim: set sw=4 sts=4 ts=8 et:
#
# PyBorg: The python AI bot.
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
import string
import os
from atomicfile import AtomicFile
import json

def _load_config_json(filename):
    """
    Load a json file containing a dict of variables.
    """
    try:
        f = open(filename, "r")
    except IOError, e:
        return None

    output = json.loads(f.read())
    f.close()

    return output

def _save_config_json(filename, fields):
    """
    Save a json file containing a dict of variables.
    """

    output = json.dumps(fields, sort_keys=True, indent=4, separators=(',',': '))

    with AtomicFile(filename, 'w') as f:
        f.write(output)


def _load_config_cfg(filename):
    """
    Load a config file returning dictionary of variables.
    """
    try:
        f = open(filename, "r")
    except IOError, e:
        return None

    stuff = {}
    line = 0

    while 1:
        line = line + 1
        s = f.readline()
        if s=="":
            break
        if s[0]=="#":
            continue

        #read if the string is above multiple lines
        while s.rfind("\\") > -1:
            s = s[:s.rfind("\\")] + f.readline()
            line = line + 1

        s = string.split(s, "=")
        if len(s) != 2:
            print "Malformed line in %s line %d" % (filename, line)
            print s
            continue
        stuff[string.strip(s[0])] = eval(string.strip(string.join(s[1:], "=")))
    return stuff

def _save_config_cfg(filename, fields):
    """
    fields should be a dictionary. Keys as names of
    variables containing tuple (string comment, value).
    """
    # Must use same dir to be truly atomic
    with AtomicFile(filename, 'w') as f:
        # write the values with comments. this is a silly comment
        for key in fields.keys():
            f.write("# "+fields[key][0]+"\n")
            s = repr(fields[key][1])
            f.write(key+"\t= ")
            if len(s) > 80:
                cut_string = ""
                while len(s) > 80:
                    position = s.rfind(",",0,80)+1
                    cut_string = cut_string + s[:position] + "\\\n\t\t"
                    s = s[position:]
                s = cut_string + s
            f.write(s+"\n")

class cfgset:
    def load(self, filename, defaults):
        """
        Defaults should be key=variable name, value=
        tuple of (comment, default value)
        """
        self._defaults = defaults
        self._filename = filename

        for i in defaults.keys():
            self.__dict__[i] = defaults[i][1]

        # try to laad saved ones
        if filename.endswith(".json"):
            vars = _load_config_json(filename)
        elif filename.endswith(".cfg"):
            vars = _load_config_cfg(filename)
        else:
            vars = None

        if vars == None:
            # none found. this is new
            self.save()
            return
        for i in vars.keys():
            self.__dict__[i] = vars[i]

    def save(self):
        """
        Save borg settings
        """
        keys = {}
        for i in self.__dict__.keys():
            # reserved
            if i == "_defaults" or i == "_filename":
                continue
            if self._defaults.has_key(i):
                comment = self._defaults[i][0]
            else:
                comment = ""
            keys[i] = (comment, self.__dict__[i])
        # save to config file
        if self._filename.endswith(".json"):
            _save_config_json(self._filename, keys)
        elif self._filename.endswith(".cfg"):
            _save_config_cfg(self._filename, keys)
        else:
            return
        #_save_config(self._filename, keys)
