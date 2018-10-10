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

#ifndef DUMP1090_ENABLED
#define DUMP1090_ENABLED 1
#endif

namespace gr {

air_modes::dump1090_proc::sptr air_modes::dump1090_proc::make(float channel_rate) {
    return gnuradio::get_initial_sptr(new air_modes::dump1090_proc_impl(channel_rate));
}

air_modes::dump1090_proc_impl::dump1090_proc_impl(float channel_rate) :
        gr::sync_block ("dump1090_proc",
        gr::io_signature::make (1, 1, sizeof(gr_complex)),
        gr::io_signature::make (0, 0, 0)),
        _lib1090BufferSize(1<<14),
        _lib1090Buffer(new sc16_t[1<<14])
{
    lib1090InitDump1090(&_fork_info);
    set_rate(channel_rate); // ????
}

air_modes::dump1090_proc_impl::~dump1090_proc_impl() {
    stop();
    //lib1090FreeDump1090(&_fork_info);
}

void air_modes::dump1090_proc_impl::set_rate(float channel_rate) {
    _fork_info->sample_rate = channel_rate;
}

float air_modes::dump1090_proc_impl::get_rate(void) {
    return _fork_info->sample_rate;
}

bool air_modes::dump1090_proc_impl::start() {
    printf("start\n");
    //lib1090InitDump1090(&_fork_info);
    int res = lib1090ForkDump1090(_fork_info);// no op if not started
    if (res == -1) { // already started

    }
    return true;
}

bool air_modes::dump1090_proc_impl::stop() {
    printf("stop\n");
#if DUMP1090_ENABLED
    lib1090KillDump1090(_fork_info);
    //lib1090FreeDump1090(&_fork_info);
#endif
    return true;
}

int air_modes::dump1090_proc_impl::work(int noutput_items,
                          gr_vector_const_void_star &input_items,
                          gr_vector_void_star &output_items)
{
    if (noutput_items > _lib1090BufferSize) {
        _lib1090BufferSize = noutput_items;
        delete [] _lib1090Buffer;
        _lib1090Buffer = new sc16_t[_lib1090BufferSize];
    }

    const gr_complex *in = (const gr_complex *) input_items[0];
    sc16_t *out = _lib1090Buffer;
    const size_t bytes = noutput_items * sizeof(sc16_t);
    //memcpy(out, in, bytes);
    //gr_complex *out = (gr_complex *) output_items[0];
    //memcpy(out, in, noutput_items * sizeof(gr_complex));

    for (int i = 0; i < noutput_items; ++i) {
        out[i][0] = (int16_t)(in[i].real() * 32768.0 * 2.0);
        out[i][1] = (int16_t)(in[i].imag() * 32768.0 * 2.0);
        //_lib1090Buffer[i][0] = (int16_t)(in[i].real() * totalGain);
        //_lib1090Buffer[i][1] = (int16_t)(in[i].imag() * totalGain);
    }

    ssize_t written = write(_fork_info->pipedes[1], _lib1090Buffer, bytes);
    if (written == -1) {
        fprintf(stderr, "write() returned error in dump1090_proc_impl::work : %d [%s]\n", errno, strerror(errno));
    } else if (written != bytes) {
        fprintf(stderr, "write() tried to write %zu bytes to pipe but only wrote %zd\n", bytes, written);
    }
    //printf("x");

    return noutput_items;
}

} //namespace gr

