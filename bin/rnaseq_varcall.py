#!/usr/bin/env python

import argparse
import re
import os
import logging

from rnaseqlib.utils import tools as ts
from rnaseqlib.utils import parse_annovar as pa
from rnaseqlib.varcall import runnables as rb


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Genetic screen workflow '
                                                 '0.0.1')
    parser.add_argument('--debug', dest='debug', required=False, type=int,
                        help='Debug level')
    parser.add_argument('--stage', dest='stage', required=False,
                        help='Limit job submission to a particular '
                             'analysis stage.'
                        '[all,alignment,extract,duplicates,splitntrim,bqsr,'
                        'bamfo,samtools,gatk,filter,dbsnp_filt,annotation]')
    parser.add_argument('--project_name', required=False, type=str,
                        help="name of the project")
    parser.add_argument('--read1', required=False, type=str,
                        help="For paired alignment, forward read.")
    parser.add_argument('--read2', required=False, type=str,
                        help="For paired alignment, reverse read.")

    parser.add_argument('--sample_dir', required=False, type=str,
                        help="Path to sample directory")
    parser.add_argument('--output_dir', required=False, type=str,
                        help="Path to output directory.")

    # aligner options
    parser.add_argument('--star_genome', required=False, type=str,
                        help="Genome directory of star aligner.")
    parser.add_argument('--ref_genome', required=False, type=str,
                        help="reference genome")
    parser.add_argument('--star2pass', required=False, action='store_true',
                        help="If set, STAR 2-pass mapping will be performed.")

    # options for region specific variant calling
    parser.add_argument('--sample_file', required=False, type=str,
                        help="For region variant calling.")
    parser.add_argument('--region', required=False, type=str, default=False,
                        help="region eg. 20:30946147-31027122")
    parser.add_argument('--num_cpus', dest='num_cpus', required=False,
                        help='Number of cpus.')

    # annovar specific options
    parser.add_argument('--annovar', required=False, type=str,
                        help="Annotate variant with annovar.")

    # defaults
    args = parser.parse_args()
    home_dir = os.getenv("HOME")

    if not args.output_dir:
        args.output_dir = os.getcwd()
    if not args.sample_dir:
        args.sample_dir = os.getcwd()
    if not args.ref_genome:
        args.defuse_ref = home_dir + "/ref_genome"
    if not args.star_genome:
        args.star_genome = home_dir + "/star_genome"
    if not args.annovar:
        args.annovar = home_dir + "/" + "src" + "/" + "annovar" + "/" + "humandb"
    if not args.num_cpus:
        args.num_cpus = "1"

    # set project directory
    project_dir = args.output_dir + "/" + args.project_name

    # create directory structure
    ts.create_output_dir(args.output_dir, args.project_name)
    sub_dir = args.output_dir + "/" + args.project_name
    ts.create_output_dir(sub_dir, "star_2pass")

    # create log file
    logfile_name = args.output_dir + "/" + args.project_name + "/" \
                   + args.project_name + ".log"
    logging.basicConfig(filename=logfile_name,
                        format='%(levelname)s: %(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        level=logging.DEBUG)

    # start analysis workflow & logging
    logging.info("RNAseq variant calling (region specific)")

    # load dictionary for file extensions
    data_dir = str(os.path.dirname(os.path.realpath(__file__)).strip('bin')) \
               + "data" + "/"
    file_ext = ts.load_dictionary(data_dir + 'file_extension.txt')
    # load dictionary for stdout messages
    stdout_msg = ts.load_dictionary(data_dir + 'stdout_message.txt')

    # start workflow
    if re.search(r"all|alignment", args.stage):

        cmd = rb.rnaseq_align(
            star_genome=args.star_genome,
            read1=args.read1,
            read2=args.read2,
            num_cpus=args.num_cpus,
            outfile_prefix=project_dir + "/"
                           + args.project_name + "."
        )

        status = ts.run_cmd(
            message=stdout_msg['alignment'],
            command=cmd,
            debug=args.debug
        )

        if args.star2pass:
            cmd = rb.star_index(
                novel_ref=project_dir + "/"
                          + "star_2pass",
                genome=args.ref_genome,
                firstroundalignment=project_dir + "/"
                                    + args.project_name + "."
                                    + file_ext['sj_out_tab'],
                sjdb_overhang="75",
                num_cpus=args.num_cpus,
                outfile_prefix=project_dir + "/"
                               + args.project_name + "."
            )

            status = ts.run_cmd(
                message=stdout_msg['alignment_index'],
                command=cmd,
                debug=args.debug
            )

            cmd = rb.rnaseq_align(
                star_genome=project_dir + "/"
                            + "star_2pass",
                read1=args.read1,
                read2=args.read2,
                num_cpus=args.num_cpus,
                outfile_prefix=project_dir + "/"
                               + args.project_name + "."
                               + "2pass_"
            )

            status = ts.run_cmd(
                message=stdout_msg['realign'],
                command=cmd,
                debug=args.debug
            )

    if re.search(r"all|extract", args.stage):

        if args.region is False:
            sample_file = project_dir + "/" \
                          + args.project_name + "." \
                          + file_ext['alignment_index']
        else:
            sample_file = args.sample_file

        cmd = rb.extract(
            input_file=sample_file,
            region=args.region,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['extract']
        )

        status = ts.run_cmd(
            message=stdout_msg['extract'],
            command=cmd,
            debug=args.debug
        )

        # reorder
        if args.region is False:
            sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['extract']
        else:
            if args.star2pass:
                sample_file = project_dir + "/" \
                              + args.project_name + "." \
                              + file_ext['star2pass']
            else:
                sample_file = project_dir + "/" \
                              + args.project_name + "." \
                              + file_ext['star_alignment']

        cmd = rb.reorder_sam(
            inbamfile=sample_file,
            outbamfile=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['reorder'],
            genome_path=args.ref_genome)

        status = ts.run_cmd(
            message=stdout_msg['reorder'],
            command=cmd,
            debug=args.debug
        )

        # sort bam
        sample_file = project_dir + "/" \
                    + args.project_name + "." \
                    + file_ext['reorder']

        cmd = rb.sort_bam(
            inbamfile=sample_file,
            outbamfile=project_dir + "/"
                        + args.project_name + "." \
                        + file_ext['sort'],
            sort_order="coordinate")

        status = ts.run_cmd(
            message=stdout_msg['sort'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|replace_rg", args.stage):

        if args.region is False:
            sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['star2pass']
        else:
            sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['sort']

        cmd = rb.replace_readgroups(
            input_file=sample_file,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['replace_rg'],
            project_name=args.project_name)

        status = ts.run_cmd(
            message=stdout_msg['replace_rg'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|duplicates", args.stage):

        sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['replace_rg']

        cmd = rb.remove_duplicates(
            inbamfile=sample_file,
            outbamfile=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['duplicates'],
            metrics_file=".duplicate_metrics.txt")

        status = ts.run_cmd(
            message=stdout_msg['duplicates'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|index", args.stage):

        sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['duplicates']

        cmd = rb.index_bam(
            inbamfile=sample_file)

        status = ts.run_cmd(
            message=stdout_msg['index'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|splitntrim", args.stage):

        sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['duplicates']

        cmd = rb.splitntrim(
            input_file=sample_file,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['splitntrim'],
            ref_genome=args.ref_genome)

        status = ts.run_cmd(
            message=stdout_msg['splitntrim'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|bqsr", args.stage):

        sample_file = project_dir + "/" \
                        + args.project_name + "." \
                        + file_ext['splitntrim']

        cmd = rb.bqsr(
            input_file=sample_file,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['bqsr'],
            ref_genome=args.ref_genome,
            recal_report=args.project_name + "."
                        + "splitntrim")

        status = ts.run_cmd(
            message=stdout_msg['bqsr'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|bamfo", args.stage):

        sample_file = project_dir + "/" \
                    + args.project_name + "." \
                    + file_ext['bqsr']

        cmd = rb.varcall_bamfo(
            input_file=sample_file,
            output_file_gatk=project_dir + "/"
                            + args.project_name + "."
                            + file_ext['bamfo'],
            ref_genome=args.ref_genome)

        status = ts.run_cmd(
            message=stdout_msg['bamfo'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|samtools", args.stage):

        sample_file = project_dir + "/" \
                    + args.project_name + "." \
                    + file_ext['bqsr']

        cmd = rb.varcall_samtools(
            input_file=sample_file,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['samtools'],
            ref_genome=args.ref_genome)

        status = ts.run_cmd(
            message=stdout_msg['samtools'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|gatk", args.stage):

        sample_file = project_dir + "/" \
                    + args.project_name + "." \
                    + file_ext['splitntrim']

        cmd = rb.varcall_gatk(
            input_file=sample_file,
            output_file_gatk=project_dir + "/"
                            + args.project_name + "."
                            + file_ext['gatk'],
            ref_genome=args.ref_genome)

        status = ts.run_cmd(
            message=stdout_msg['gatk'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|variant_filtering", args.stage):

        #only gatk
        sample_file = project_dir + "/" \
                    + args.project_name + "." \
                    + file_ext['gatk']

        cmd = rb.variant_filtering(
            input_file=sample_file,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['filtering'],
            ref_genome=args.ref_genome)

        status = ts.run_cmd(
            message=stdout_msg['filtering'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|snpdb_filt", args.stage):

        sample_file = project_dir + "/" \
                    + args.project_name + "." \
                    + file_ext['filtering']

        cmd = rb.convert2annovar(
            input_file=sample_file,
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['annotation']
        )

        status = ts.run_cmd(
            message=stdout_msg['annotation'],
            command=cmd,
            debug=args.debug
        )

        cmd = rb.dbsnp_filter(
            dbtype="snp138NonFlagged",
            buildversion="hg19",
            input_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['annotation'] + "."
                        + "annovar",
            annovar_dir=args.annovar
        )

        status = ts.run_cmd(
            message=stdout_msg['dbsnp'],
            command=cmd,
            debug=args.debug
        )

    if re.search(r"all|annotation", args.stage):

        sample_file = project_dir + "/" \
                      + args.project_name + "." \
                      + file_ext['annotation'] + "." \
                      + "annovar" + "." \
                      + file_ext['dbsnp']


        cmd = rb.gene_annotation(
            buildversion="hg19",
            input_file=sample_file,
            annovar_dir=args.annovar
        )

        status = ts.run_cmd(
            message=stdout_msg['geneanno'],
            command=cmd,
            debug=args.debug
        )

        pa.parse_variant(
            input_file=project_dir + "/"
                       + args.project_name + "."
                       + file_ext['annotation'] + "."
                       + "annovar" + "."
                       + file_ext['dbsnp'] + "."
                       + file_ext['variant'],
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['annotation'] + "."
                        + "annovar" + "."
                        + file_ext['dbsnp'] + "."
                        + file_ext['variant'] + "."
                        + file_ext['keep']
        )

        pa.parse_exonic(
            input_file=project_dir + "/"
                       + args.project_name + "."
                       + file_ext['annotation'] + "."
                       + "annovar" + "."
                       + file_ext['dbsnp'] + "."
                       + file_ext['exonic'],
            output_file=project_dir + "/"
                        + args.project_name + "."
                        + file_ext['annotation'] + "."
                        + "annovar" + "."
                        + file_ext['dbsnp'] + "."
                        + file_ext['exonic'] + "."
                        + file_ext['keep']
        )


