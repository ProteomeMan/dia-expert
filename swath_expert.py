#!/usr/bin/python

__author__ = 'Tiannan Guo, ETH Zurich 2015'

# this software reads in chromatographic text files, and openSWATH identification results,
# and refine fragments, perform quantification of fragments and peptides.

import os
import sys
import time
import swath_quant
import io_swath
import peak_groups
import r_code
import chrom
import parameters as param
from whichcraft import which

import argparse

def print_help():
    print
    print "python %s accepts the following command line arguments:" % sys.argv[0]
    print
    print "   <chromatogram_file>:  path to chromatogram_file to process (mandatory)"
    print "   <path_to_rcmd_exe> :  path to Rcmd.exe or RScript on your computer (optional)"
    print
#
# if len(sys.argv) < 2:
#     print_help()
#     sys.exit(1)
#
# chrom_file = "test1.txt.gz"
# # chrom_file = "com_chrom_9_9.txt.gz"
# id_mapping_file = "pcf224sw_b.txt"
# tic_normalization_file = "pcf224sw_TIC_ms1.txt"

# modified by Wu Jianfeng
# use argparse to parse arguments

parser = argparse.ArgumentParser(description="swath expert")

parser.add_argument("--map_file", required=True,
    help="samples mapping file. eg, 'goldenSets90.txt'")

parser.add_argument("--chrom_file", required=True,
    help="eg, com_chrom_1.txt.gz")

parser.add_argument("--tic_file", required=True,
    help="tic file. #eg, 'gold90.tic'")

parser.add_argument("--use_ms2", action='store_true',
    help="use ms2 tic if specified.")

args = parser.parse_args()

chrom_file = args.chrom_file
id_mapping_file = args.map_file
tic_normalization_file = args.tic_file

# modified by Wu Jianfeng
# default tic key is ms1_tic
tic_key = "ms1_tic"
if args.use_ms2:
    tic_key = "ms2_tic"

def remove_all_file_extensions(path):
    path = os.path.splitext(path)[0]
    while True:
        path, ext = os.path.splitext(path)
        if ext == "":
            return path

name_stem = remove_all_file_extensions(chrom_file)

out_R_file = name_stem + '.R'
out_file_poor_tg = name_stem + '.poor.txt'
quant_file_fragments = name_stem + '.quant.fragments.txt'
quant_file_peptides = name_stem + '.quant.peptides.txt'
quant_file_proteins = name_stem + '.quant.proteins.txt'

if sys.platform == "win32":
    batch_file = name_stem + ".bat"
else:
    batch_file = name_stem + ".sh"


def check_r():
    if len(sys.argv) == 3:
        r_path = sys.argv[2]
    elif sys.platform == 'win32':
        r_path = r'C:\R\R-2.15.1\bin\x64\Rcmd.exe'
    elif sys.platform in ('linux', 'darwin'):
        r_path = which('RScript')  # might return None
    else:
        raise Exception("platform %r not supported (yet)" % sys.platform)

    if r_path is None or not os.path.exists(r_path):
        print
        print "could not find R interpreter at %r" % r_path
        print_help()
        sys.exit(1)
    return r_path


def write_bat_file(out_R_file, batch_file):
    with open(batch_file, 'w') as o:
        if param.platform == 'linux':
            cmd = 'R CMD BATCH ' % (out_R_file)
        elif param.platform == 'tiannan_windows':
            cmd = 'C:\R\R-2.15.1\bin\x64\Rcmd.exe %s\n' % out_R_file
        o.write(cmd)
        o.write('\n')


def main(tic_key):

    # read input file of sample information
    sample_id, id_mapping = io_swath.read_id_file(id_mapping_file)

    normalization_factors = io_swath.read_tic_normalization_file(tic_normalization_file, tic_key)

    # read input chrom file,
    # build chrom_data, find peaks when the class is initialized
    ref_sample_data, chrom_data, peptide_data = io_swath.read_com_chrom_file(
        chrom_file, sample_id, normalization_factors)

    # based on peaks of fragments, keep peak groups with at least MIN_FRAGMENT
    # fragment, find out peak boundary of each fragment
    peak_group_candidates = peak_groups.find_peak_group_candidates(chrom_data, sample_id)

    # based on peak groups found in the reference sample, find out fragments
    # that form good peaks, remove the rest fragments
    ref_sample_data, chrom_data, peptide_data, peak_group_candidates = \
        peak_groups.refine_peak_forming_fragments_based_on_reference_sample(
            ref_sample_data, chrom_data, peptide_data, peak_group_candidates)

    # compute the peak boundary for the reference sample, write to display_pg
    display_data, peak_group_candidates, chrom_data = \
        chrom.compute_reference_sample_peak_boundary(ref_sample_data, chrom_data,
                                                     peptide_data, peak_group_candidates)

    # based on the display_data for reference sample, get the best matched peak groups from all other samples
    # and then write to display_data
    display_data = peak_groups.find_best_peak_group_based_on_reference_sample(
        display_data, ref_sample_data, chrom_data, peptide_data, peak_group_candidates, sample_id)

    # compute peak area for display_pg
    display_data = chrom.compute_peak_area_for_all(display_data)

    # compute peak area for only the peak-forming fragments
    display_data = swath_quant.compute_peak_area_for_refined_fragment(
        display_data, sample_id, ref_sample_data, quant_file_fragments)

    # compute peptide area
    swath_quant.compute_peptide_intensity_based_on_median_ratio_of_fragments(
        quant_file_peptides, quant_file_fragments, sample_id, ref_sample_data, display_data)

    # write r code into a file
    r_code.write_r_code_for_all_samples(display_data, sample_id, out_R_file, ref_sample_data)


start_time = time.time()
print "--- start processing ---"
main(tic_key)
print "--- %s seconds ---" % (time.time() - start_time)
