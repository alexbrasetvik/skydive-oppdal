#!/usr/bin/env python

# pip install watchdog
# watchmedo shell-command --patterns='*.wtf;*' --recursive --command='find "${watch_src_path}" -iname *.handlebars | xargs ./compile_handlebars.py' templates

import os
import sys


def compile(filename):
    return os.popen('handlebars -s "%s"' % filename).read()


for filename in sys.argv[1:]:
    template = compile(filename)
    output_filename = filename.rsplit('.', 1)[0] + '.template.js'
    file = open(output_filename, 'w')
    file.write("define(['handlebars.vm'], function(Handlebars) { "
               "return Handlebars.template(%s);"
               "});" % template)

    print '%s -> %s' % (filename, output_filename)
