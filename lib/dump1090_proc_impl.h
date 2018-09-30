/*
# Copyright (C) 2013 Nick Foster
  Copyright (C) 2018 Paul Ciarlo
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

#ifndef INCLUDED_AIR_MODES_DUMP1090_PROC_IMPL_H
#define INCLUDED_AIR_MODES_DUMP1090_PROC_IMPL_H

#include <gnuradio/sync_block.h>
#include <gnuradio/msg_queue.h>
#include <gr_air_modes/api.h>
#include <gr_air_modes/dump1090_proc.h>
#include <lib1090.h>

namespace gr {
namespace air_modes {

class AIR_MODES_API dump1090_proc_impl : public dump1090_proc
{
private:
    struct dump1090Fork_t *_fork_info;

public:
    dump1090_proc_impl(float channel_rate);
    virtual ~dump1090_proc_impl();

    int work (int noutput_items,
              gr_vector_const_void_star &input_items,
              gr_vector_void_star &output_items);

    virtual void set_rate(float channel_rate);
    virtual float get_rate(void);

    virtual bool start();
    virtual bool stop();
};

} //namespace air_modes
} //namespace gr

#endif /* INCLUDED_AIR_MODES_DUMP1090_PROC_IMPL_H */

