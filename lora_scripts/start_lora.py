#!/usr/bin/env python3
import sys
import numpy as np
from gnuradio import gr, network
import osmosdr
from gnuradio import lora_sdr

class lora_rx_custom(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "Lora Rx (RTL-SDR to UDP)")

        # Parameters
        self.soft_decoding = True
        self.sf = 7
        self.samp_rate = 1000000
        self.pay_len = 11
        self.impl_head = False
        self.has_crc = True
        self.cr = 1
        self.center_freq = 433e6
        self.bw = 125000

        # Blocks
        self.rtlsdr_source = osmosdr.source(args="numrecv=1")
        self.rtlsdr_source.set_sample_rate(self.samp_rate)
        self.rtlsdr_source.set_center_freq(self.center_freq, 0)
        self.rtlsdr_source.set_freq_corr(0, 0)
        self.rtlsdr_source.set_dc_offset_mode(0, 0)
        self.rtlsdr_source.set_iq_balance_mode(0, 0)
        self.rtlsdr_source.set_gain_mode(False, 0)
        self.rtlsdr_source.set_gain(40, 0)
        self.rtlsdr_source.set_if_gain(20, 0)
        self.rtlsdr_source.set_bb_gain(20, 0)
        self.rtlsdr_source.set_antenna('', 0)
        self.rtlsdr_source.set_bandwidth(0, 0)

        self.lora_sdr_header_decoder_0 = lora_sdr.header_decoder(self.impl_head, self.cr, self.pay_len, self.has_crc, False, True)
        self.lora_sdr_hamming_dec_0 = lora_sdr.hamming_dec(self.soft_decoding)
        self.lora_sdr_gray_mapping_0 = lora_sdr.gray_mapping(self.soft_decoding)
        self.lora_sdr_frame_sync_0 = lora_sdr.frame_sync(int(self.center_freq), self.bw, self.sf, self.impl_head, [18], int(self.samp_rate/self.bw), 8)
        self.lora_sdr_fft_demod_0 = lora_sdr.fft_demod(self.soft_decoding, True)
        self.lora_sdr_dewhitening_0 = lora_sdr.dewhitening()
        self.lora_sdr_deinterleaver_0 = lora_sdr.deinterleaver(self.soft_decoding)
        self.lora_sdr_crc_verif_0 = lora_sdr.crc_verif(1, False)

        # Output to UDP for Dashboard (Port 52001)
        self.udp_sink = network.udp_sink(gr.sizeof_char, 1, "127.0.0.1", 52001, 0, 1472, False)

        # Connections
        self.msg_connect((self.lora_sdr_header_decoder_0, 'frame_info'), (self.lora_sdr_frame_sync_0, 'frame_info'))
        
        self.connect((self.rtlsdr_source, 0), (self.lora_sdr_frame_sync_0, 0))
        self.connect((self.lora_sdr_frame_sync_0, 0), (self.lora_sdr_fft_demod_0, 0))
        self.connect((self.lora_sdr_fft_demod_0, 0), (self.lora_sdr_gray_mapping_0, 0))
        self.connect((self.lora_sdr_gray_mapping_0, 0), (self.lora_sdr_deinterleaver_0, 0))
        self.connect((self.lora_sdr_deinterleaver_0, 0), (self.lora_sdr_hamming_dec_0, 0))
        self.connect((self.lora_sdr_hamming_dec_0, 0), (self.lora_sdr_header_decoder_0, 0))
        self.connect((self.lora_sdr_header_decoder_0, 0), (self.lora_sdr_dewhitening_0, 0))
        self.connect((self.lora_sdr_dewhitening_0, 0), (self.lora_sdr_crc_verif_0, 0))
        
        # We NO LONGER connect crc_verif_0 to udp_sink_0!
        # The wrapper pipe_lora.py will handle reading stdout and forwarding it cleanly!

def main():
    tb = lora_rx_custom()
    print("Starting RTL-SDR LoRa Decoder -> UDP(52001)")
    tb.start()
    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()

if __name__ == '__main__':
    main()
