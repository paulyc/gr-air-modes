/*
# Copyright 2010 Nick Foster
# Copyright 2013 Nicholas Corgan
#
# This file is part of gr-air-modes
#
# gr-air-modes is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# gr-air-modes is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gr-air-modes; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#
*/

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <ciso646>
#include "dump1090_proc_impl.h"
#include <gnuradio/io_signature.h>
#include <string.h>
#include <iostream>
#include <gnuradio/tags.h>

namespace gr {

air_modes::dump1090_proc::sptr air_modes::dump1090_proc::make(float channel_rate) {
    return gnuradio::get_initial_sptr(new air_modes::dump1090_proc_impl(channel_rate));
}

air_modes::dump1090_proc_impl::dump1090_proc_impl(float channel_rate) :
        gr::sync_block ("dump1090_proc",
           gr::io_signature::make (1, 1, sizeof(gr_complex)), //raw I/Q samples straight thru
           gr::io_signature::make (1, 1, sizeof(gr_complex)))
{
    lib1090InitDump1090Fork(&_fork_info);
    set_rate(channel_rate);
}

air_modes::dump1090_proc_impl::~dump1090_proc_impl() {
    stop();
    lib1090FreeDump1090Fork(&_fork_info);
}

void air_modes::dump1090_proc_impl::set_rate(float channel_rate) {
    _fork_info->sample_rate = channel_rate;
}

float air_modes::dump1090_proc_impl::get_rate(void) {
    return _fork_info->sample_rate;
}

bool air_modes::dump1090_proc_impl::start() {
    if (lib1090RunDump1090Fork(_fork_info) != 0) {
        return false;
    }
    return true;
}

bool air_modes::dump1090_proc_impl::stop() {
    lib1090KillDump1090Fork(_fork_info);
    return true;
}

int air_modes::dump1090_proc_impl::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
                          gr_vector_void_star &output_items)
{
    const gr_complex *in = (const gr_complex *) input_items[0];
    gr_complex *out = (gr_complex *) output_items[0];
    memcpy(out, in, noutput_items * sizeof(gr_complex));
    const size_t bytes = sizeof(gr_complex) * noutput_items;
    ssize_t written = write(_fork_info->pipedes[0], in, bytes);
    if (written == -1) {
        fprintf(stderr, "write() returned error in dump1090_proc_impl::work : %d [%s]\n", errno, strerror(errno));
    } else if (written != bytes) {
        fprintf(stderr, "write() tried to write %zu bytes to pipe but only wrote %zs\n", bytes, written);
    }

    return WORK_DONE;
}

} //namespace gr

