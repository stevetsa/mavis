import os
import sys
import itertools


# local modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ..breakpoint import BreakpointPair
from .cluster import cluster_breakpoint_pairs
from ..constants import COLUMNS
from ..interval import Interval
from ..pipeline.util import read_inputs, output_tabbed_file, write_bed_file
from ..pipeline.util import build_batch_id, filter_on_overlap, log, mkdirp


def main(
    inputs, output, stranded_bam, library, protocol,
    masking, cluster_clique_size, cluster_radius, uninformative_filter, max_proximity,
    annotations, min_clusters_per_file, max_files, **kwargs
):
    # output files
    cluster_batch_id = build_batch_id(prefix='cluster-')
    UNINFORM_OUTPUT = os.path.join(output, 'uninformative_clusters.txt')
    CLUSTER_ASSIGN_OUTPUT = os.path.join(output, 'cluster_assignment.tab')
    CLUSTER_BED_OUTPUT = os.path.join(output, 'clusters.bed')
    split_file_name_func = lambda x: os.path.join(output, '{}-{}.tab'.format(cluster_batch_id, x))
    # load the input files
    temp = read_inputs(
        inputs, stranded_bam,
        cast={COLUMNS.tools: lambda x: set(x.split(';')) if x else set()},
        add={COLUMNS.library: library, COLUMNS.protocol: protocol}
    )
    breakpoint_pairs = []
    for bpp in temp:
        if bpp.data[COLUMNS.library] == library and bpp.data[COLUMNS.protocol] == protocol:
            breakpoint_pairs.append(bpp)
    # filter by masking file
    breakpoint_pairs, filtered_bpp = filter_on_overlap(breakpoint_pairs, masking)

    log('computing clusters')
    clusters = cluster_breakpoint_pairs(breakpoint_pairs, r=cluster_radius, k=cluster_clique_size)

    hist = {}
    length_hist = {}
    for index, cluster in enumerate(clusters):
        input_pairs = clusters[cluster]
        hist[len(input_pairs)] = hist.get(len(input_pairs), 0) + 1
        c1 = round(len(cluster[0]), -2)
        c2 = round(len(cluster[1]), -2)
        length_hist[c1] = length_hist.get(c1, 0) + 1
        length_hist[c2] = length_hist.get(c2, 0) + 1
        cluster.data[COLUMNS.cluster_id] = '{}-{}'.format(cluster_batch_id, index + 1)
        cluster.data[COLUMNS.cluster_size] = len(input_pairs)
        temp = set()
        for p in input_pairs:
            temp.update(p.data[COLUMNS.tools])
        cluster.data[COLUMNS.tools] = ';'.join(sorted(list(temp)))
    log('computed', len(clusters), 'clusters', time_stamp=False)
    log('cluster input pairs distribution', sorted(hist.items()), time_stamp=False)
    log('cluster intervals lengths', sorted(length_hist.items()), time_stamp=False)
    # map input pairs to cluster ids
    # now create the mapping from the original input files to the cluster(s)
    mkdirp(output)

    with open(CLUSTER_ASSIGN_OUTPUT, 'w') as fh:
        header = set()
        rows = {}

        for cluster, input_pairs in clusters.items():
            for p in input_pairs:
                if p in rows:
                    rows[p][COLUMNS.tools].update(p.data[COLUMNS.tools])
                else:
                    rows[p] = BreakpointPair.flatten(p)
                rows[p].setdefault('clusters', set()).add(cluster.data[COLUMNS.cluster_id])
        for row in rows.values():
            row['clusters'] = ';'.join([str(c) for c in sorted(list(row['clusters']))])
            row[COLUMNS.tools] = ';'.join(sorted(list(row[COLUMNS.tools])))
            row[COLUMNS.library] = library
            row[COLUMNS.protocol] = protocol
        output_tabbed_file(rows, CLUSTER_ASSIGN_OUTPUT)

    output_files = []
    # filter clusters based on annotations
    # decide on the number of clusters to validate per job
    pass_clusters = list(clusters)
    fail_clusters = []

    if uninformative_filter:
        pass_clusters = []
        for cluster in clusters:
            # loop over the annotations
            overlaps_gene = False
            w1 = Interval(cluster.break1.start - max_proximity, cluster.break1.end + max_proximity)
            w2 = Interval(cluster.break2.start - max_proximity, cluster.break2.end + max_proximity)
            for gene in annotations.get(cluster.break1.chr, []):
                if Interval.overlaps(gene, w1):
                    overlaps_gene = True
                    break
            for gene in annotations.get(cluster.break2.chr, []):
                if Interval.overlaps(gene, w2):
                    overlaps_gene = True
                    break
            if overlaps_gene:
                pass_clusters.append(cluster)
            else:
                fail_clusters.append(cluster)
    if len(fail_clusters) + len(pass_clusters) != len(clusters):
        raise AssertionError(
            'totals do not add up', len(fail_clusters), len(pass_clusters), 'does not total to', len(clusters))
    log('filtered', len(fail_clusters), 'clusters as not informative')
    output_tabbed_file(fail_clusters, UNINFORM_OUTPUT)

    JOB_SIZE = min_clusters_per_file
    if len(pass_clusters) // min_clusters_per_file > max_files - 1:
        JOB_SIZE = len(pass_clusters) // max_files
        assert(len(pass_clusters) // JOB_SIZE == max_files)

    bedfile = os.path.join(output, 'clusters.bed')
    write_bed_file(bedfile, itertools.chain.from_iterable([b.get_bed_repesentation() for b in pass_clusters]))

    job_ranges = list(range(0, len(pass_clusters), JOB_SIZE))
    if job_ranges[-1] != len(pass_clusters):
        job_ranges.append(len(pass_clusters))
    job_ranges = zip(job_ranges, job_ranges[1::])

    for i, jrange in enumerate(job_ranges):
        # generate an output file
        filename = split_file_name_func(i + 1)
        output_files.append(filename)
        output_tabbed_file(pass_clusters[jrange[0]:jrange[1]], filename)

    return output_files
