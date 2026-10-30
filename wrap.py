#!/usr/bin/env python3
"""Wrap the build_page.py fragment into a standalone HTML document for GitHub Pages."""
import sys
frag = open(sys.argv[1]).read()
head = ('<!doctype html><html lang="en-CA"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="robots" content="noindex">'
        '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style></head><body>')
open(sys.argv[2], "w").write(head + frag + "</body></html>")
