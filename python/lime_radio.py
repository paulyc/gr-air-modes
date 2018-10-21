# Copyright (C) 2018 Paul Ciarlo

from gnuradio import gr, gru, eng_notation, filter, blocks
from gnuradio.filter import optfir
from gnuradio.eng_option import eng_option
from gnuradio.gr.pubsub import pubsub
from gnuradio.filter import pfb
from optparse import OptionParser, OptionGroup
import air_modes
import zmq
import threading
import time
import re

class lime_rx_path (gr.hier_block2):
    OUTPUT_RATE = 2400000.0
    def __init__(self, rx_rate, threshold, queue, pmf=False, dcblock=False):
        gr.hier_block2.__init__(self, "lime_rx_path",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex),
                                gr.io_signature(0,0,0))

        self._rx_rate = rx_rate
        self._threshold = threshold
        self._queue = queue
        self._pmf = pmf
        self._dcblock = dcblock
        self._resample = pfb.arb_resampler_ccf(lime_rx_path.OUTPUT_RATE/self._rx_rate)
        self._tcp_server_sink = blocks.tcp_server_sink(gr.sizeof_short, "127.0.0.1", 29999, False)
        self._multiply = blocks.multiply_const_cc(32768.0)
        self._demod = blocks.complex_to_interleaved_short()
        self.connect(self, self._resample, self._multiply, self._demod, self._tcp_server_sink)

    def set_rate(self, rx_rate):
        self._rx_rate = rx_rate
        self._resample.set_rate(lime_rx_path.OUTPUT_RATE/rx_rate)

    def set_threshold(self, threshold):
        pass ##self._sync.set_threshold(threshold)

    def set_pmf(self, pmf):
        pass #TODO must be done when top block is stopped

    def get_pmf(self, pmf):
        pass # return not (self._bb == self._demod)

    def get_threshold(self):
        return 0.0 #return self._sync.get_threshold()

class lime_radio (gr.top_block, pubsub):
    def __init__(self, options, context):
        gr.top_block.__init__(self)
        pubsub.__init__(self)

        self._options = options
        self._queue = gr.msg_queue()
        self._rx_rate = options.rate

        self._setup_source(options)

        self._rx_path = lime_rx_path(self._rx_rate, options.threshold,
                                      self._queue, options.pmf, options.dcblock)

        self.connect(self._u, self._rx_path)

        #now subscribe to set various options via pubsub
        self.subscribe("freq", self.set_freq)
        self.subscribe("gain", self.set_gain)
        self.subscribe("rate", self.set_rate)
        self.subscribe("rate", self._rx_path.set_rate)
        self.subscribe("threshold", self._rx_path.set_threshold)
        self.subscribe("pmf", self._rx_path.set_pmf)

        self.publish("freq", self.get_freq)
        self.publish("gain", self.get_gain)
        self.publish("rate", self.get_rate)
        self.publish("threshold", self._rx_path.get_threshold)
        self.publish("pmf", self._rx_path.get_pmf)

        #Publish messages when they come back off the queue
        server_addr = ["inproc://modes-radio-pub"]
        if options.tcp is not None:
            server_addr += ["tcp://*:%i" % options.tcp]

        self._sender = air_modes.zmq_pubsub_iface(context, subaddr=None, pubaddr=server_addr)
        self._async_sender = gru.msgq_runner(self._queue, self.send)
        
    def send(self, msg):
        self._sender["dl_data"] = msg.to_string()
    
    @staticmethod
    def add_radio_options(parser):
        group = OptionGroup(parser, "Receiver setup options")

        #Choose source
        group.add_option("-s","--source", type="string", default="uhd",
            help="Choose source: uhd, osmocom, <filename>, or <ip:port> [default=%default]")
        group.add_option("-t","--tcp", type="int", default=None, metavar="PORT",
            help="Open a TCP server on this port to publish reports")

        #UHD/Osmocom args
        group.add_option("-R", "--subdev", type="string",
                        help="select USRP Rx side A or B", metavar="SUBDEV")
        group.add_option("-A", "--antenna", type="string",
                        help="select which antenna to use on daughterboard")
        group.add_option("-D", "--args", type="string",
                        help="arguments to pass to radio constructor", default="")
        group.add_option("-f", "--freq", type="eng_float", default=1090e6,
                        help="set receive frequency in Hz [default=%default]", metavar="FREQ")
        group.add_option("-g", "--gain", type="int", default=None,
                        help="set RF gain", metavar="dB")

        #RX path args
        group.add_option("-r", "--rate", type="eng_float", default=4e6,
                        help="set sample rate [default=%default]")
        group.add_option("-T", "--threshold", type="eng_float", default=7.0,
                        help="set pulse detection threshold above noise in dB [default=%default]")
        group.add_option("-p","--pmf", action="store_true", default=False,
                        help="Use pulse matched filtering [default=%default]")
        group.add_option("-d","--dcblock", action="store_true", default=False,
                        help="Use a DC blocking filter (best for HackRF Jawbreaker) [default=%default]")
                     
        parser.add_option_group(group)
        
    def live_source(self):
        return self._options.source=="uhd" or self._options.source=="osmocom"
    
    def set_freq(self, freq):
        return self._u.set_center_freq(freq, 0) if self.live_source() else 0
        
    def set_gain(self, gain):
        if self.live_source():
            self._u.set_gain(gain)
            print "Gain is %f" % self.get_gain()
            return self.get_gain()
        
    def set_rate(self, rate):
        self._rx_rate = rate
        self._rx_path.set_rate(self._rx_rate)
        if self._options.source in ("osmocom"):
            return self._u.set_sample_rate(rate)
        if self._options.source in ("uhd"):
            return self._u.set_rate(rate)
        else:
            return 0
            
    def set_threshold(self, threshold):
        self._rx_path.set_threshold(threshold)
    
    def get_freq(self, freq):
        return self._u.get_center_freq(freq, 0) if self.live_source() else 1090e6
        
    def get_gain(self):
        return self._u.get_gain() if self.live_source() else 0
    
    def get_rate(self):
        return self._u.get_rate() if self.live_source() else self._rate
        
    def _setup_source(self, options):
        if options.source == "uhd":
            #UHD source by default
            from gnuradio import uhd
            sa = uhd.stream_args("fc32", "sc16")
            self._u = uhd.single_usrp_source(options.args, sa)
    #      self._u = uhd.single_usrp_source(options.args, uhd.io_type_t.COMPLEX_FLOAT32, 1)

            if(options.subdev):
                self._u.set_subdev_spec(options.subdev, 0)

            if not self._u.set_center_freq(options.freq):
                print "Failed to set initial frequency"

            # LimeSDR Mini insists we set sample rate before setting time
            self._u.set_samp_rate(options.rate)
            options.rate = int(self._u.get_samp_rate()) #retrieve actual

            #check for GPSDO
            #if you have a GPSDO, UHD will automatically set the timestamp to UTC time
            #as well as automatically set the clock to lock to GPSDO.
            if self._u.get_time_source(0) != 'gpsdo':
                self._u.set_time_now(uhd.time_spec(0.0))

            if options.antenna is not None:
                self._u.set_antenna(options.antenna)

            if options.gain is None: #set to halfway
                g = self._u.get_gain_range()
                options.gain = (g.start()+g.stop()) / 2.0

            print "Setting gain to %i" % options.gain
            self._u.set_gain(options.gain)
            print "Gain is %i" % self._u.get_gain()

        #TODO: detect if you're using an RTLSDR or Jawbreaker
        #and set up accordingly.
        elif options.source == "osmocom": #RTLSDR dongle or HackRF Jawbreaker
            import osmosdr
            self._u = osmosdr.source(options.args)
        #   self._u.set_sample_rate(3.2e6) #fixed for RTL dongles
            self._u.set_sample_rate(options.rate)
            if not self._u.set_center_freq(options.freq):
                print "Failed to set initial frequency"

            #   self._u.set_gain_mode(0) #manual gain mode
            if options.gain is None:
                options.gain = 34
            self._u.set_gain(options.gain)
            print "Gain is %i" % self._u.get_gain()

#Note: this should only come into play if using an RTLSDR.
#        lpfiltcoeffs = gr.firdes.low_pass(1, 5*3.2e6, 1.6e6, 300e3)
#        self._resample = filter.rational_resampler_ccf(interpolation=5, decimation=4, taps=lpfiltcoeffs)

        else:
            #semantically detect whether it's ip.ip.ip.ip:port or filename
            if ':' in options.source:
                try:
                    ip, port = re.search("(.*)\:(\d{1,5})", options.source).groups()
                except:
                    raise Exception("Please input UDP source e.g. 192.168.10.1:12345")

                self._u = blocks.udp_source(gr.sizeof_gr_complex, ip, int(port))
                print "Using UDP source %s:%s" % (ip, port)
            else:
                self._u = blocks.file_source(gr.sizeof_gr_complex, options.source)
                print "Using file source %s" % options.source

        print "Rate is %i" % (options.rate,)
    
    def close(self):
        self.stop()
        self.wait()
        self._sender.close()
        self._u = None

def main():
    my_position = None
    usage = "%prog: [options]"
    optparser = OptionParser(option_class=eng_option, usage=usage)
    air_modes.modes_radio.add_radio_options(optparser)

    optparser.add_option("-l","--location", type="string", default=None,
                        help="GPS coordinates of receiving station in format xx.xxxxx,xx.xxxxx")
    #data source options
    optparser.add_option("-a","--remote", type="string", default=None,
                        help="specify additional servers from which to take data in format tcp://x.x.x.x:y,tcp://....")
    optparser.add_option("-n","--no-print", action="store_true", default=False,
                        help="disable printing decoded packets to stdout")
    #output plugins
    optparser.add_option("-K","--kml", type="string", default=None,
                        help="filename for Google Earth KML output")
    optparser.add_option("-P","--sbs1", action="store_true", default=False,
                        help="open an SBS-1-compatible server on port 30003")
    optparser.add_option("-m","--multiplayer", type="string", default=None,
                        help="FlightGear server to send aircraft data, in format host:port")

    (options, args) = optparser.parse_args()

    #construct the radio
    context = zmq.Context(1)
    tb = lime_radio(options, context)
    servers = ["inproc://modes-radio-pub"]
    if options.remote is not None:
        servers += options.remote.split(",")
    relay = air_modes.zmq_pubsub_iface(context, subaddr=servers, pubaddr=None)
    publisher = pubsub()
    relay.subscribe("dl_data", air_modes.make_parser(publisher))
    tb.run()
    time.sleep(0.2)
    tb.close()
    time.sleep(0.2)
    relay.close()

if __name__ == '__main__':
    main()