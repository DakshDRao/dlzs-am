# dirs.mk -- directory anchors, included FIRST by every tb/<name>/Makefile.
#
# Split out from common.mk because of a make ordering trap: common.mk does
# `VERILOG_SOURCES += dump_waves.v` under WAVES=1, so if a bench Makefile set
# VERILOG_SOURCES with `:=` *after* including it, that append was silently
# discarded and WAVES=1 failed elaboration. Anchors first, then sources, then
# common.mk last.
#
# firstword $(MAKEFILE_LIST) is the bench Makefile that make was invoked on,
# so TBDIR resolves to tb/<name>/ whichever fragment asks.
TBDIR   := $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))
ROOT    := $(abspath $(TBDIR)/../..)
RTLDIR  := $(ROOT)/rtl
DRUMDIR := $(ROOT)/baselines/drum
SRCDIR  := $(ROOT)/src
