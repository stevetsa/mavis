from mavis.breakpoint import Breakpoint
from mavis.annotate import load_reference_genome
from mavis.constants import ORIENT, PYSAM_READ_FLAGS
from mavis.bam.cache import BamCache
from . import MockRead, mock_read_pair
import unittest
from . import REFERENCE_GENOME_FILE, BAM_INPUT, FULL_BAM_INPUT, RUN_FULL
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from mavis.validate.evidence import GenomeEvidence

REFERENCE_GENOME = None


def setUpModule():
    global REFERENCE_GENOME
    REFERENCE_GENOME = load_reference_genome(REFERENCE_GENOME_FILE)
    if 'CTCCAAAGAAATTGTAGTTTTCTTCTGGCTTAGAGGTAGATCATCTTGGT' != REFERENCE_GENOME['fake'].seq[0:50].upper():
        raise AssertionError('fake genome file does not have the expected contents')
    global BAM_CACHE
    BAM_CACHE = BamCache(BAM_INPUT)
    global FULL_BAM_CACHE
    FULL_BAM_CACHE = BamCache(FULL_BAM_INPUT)
    global READS
    READS = {}
    for read in BAM_CACHE.fetch('reference3', 1, 8000):
        if read.qname not in READS:
            READS[read.qname] = [None, None]
        if read.is_supplementary:
            continue
        if read.is_read1:
            READS[read.qname][0] = read
        else:
            READS[read.qname][1] = read
    # add a check to determine if it is the expected bam file


@unittest.skipIf(not RUN_FULL, 'slower tests will not be run unless the environment variable RUN_FULL is given')
class TestFullEvidenceGathering(unittest.TestCase):
    # need to make the assertions more specific by checking the actual names of the reads found in each bin
    # rather than just the counts.
    def genome_evidence(self, break1, break2, opposing_strands):
        ge = GenomeEvidence(
            break1, break2, FULL_BAM_CACHE, REFERENCE_GENOME,
            opposing_strands=opposing_strands,
            read_length=125,
            stdev_fragment_size=100,
            median_fragment_size=380,
            stdev_count_abnormal=3,
            min_flanking_pairs_resolution=3,
            max_sc_preceeding_anchor=3
        )
        print(ge.break1.chr, ge.outer_windows[0])
        print(ge.break1.chr, ge.inner_windows[0])
        print(ge.break2.chr, ge.outer_windows[1])
        print(ge.break2.chr, ge.inner_windows[1])
        return ge

    def count_original_reads(self, reads):
        count = 0
        for read in sorted(reads, key=lambda x: x.query_name):
            if not read.has_tag(PYSAM_READ_FLAGS.TARGETED_ALIGNMENT):
                count += 1
            elif not read.get_tag(PYSAM_READ_FLAGS.TARGETED_ALIGNMENT):
                count += 1
        return count

    def test_load_evidence_translocation(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 520, orient=ORIENT.RIGHT),
            Breakpoint('reference19', 964, orient=ORIENT.LEFT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(14, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(20, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(21, len(ev1.flanking_pairs))

        # second example
        ev1 = self.genome_evidence(
            Breakpoint('reference2', 2000, orient=ORIENT.LEFT),
            Breakpoint('reference4', 2000, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(21, self.count_original_reads(ev1.split_reads[0]))
        # one of the reads that appears to look good in the bam is too low quality % match
        self.assertEqual(40, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(57, len(ev1.flanking_pairs))

    def test_load_evidence_inversion(self):
        # first example
        ev1 = self.genome_evidence(
            Breakpoint('reference3', 1114, orient=ORIENT.RIGHT),
            Breakpoint('reference3', 2187, orient=ORIENT.RIGHT),
            opposing_strands=True
        )

        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(54, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(20, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(104, len(ev1.flanking_pairs))

        # second example
        ev1 = self.genome_evidence(
            Breakpoint('reference7', 15000, orient=ORIENT.RIGHT),
            Breakpoint('reference7', 19000, orient=ORIENT.RIGHT),
            opposing_strands=True
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(15, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(27, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(52, len(ev1.flanking_pairs))

    def test_load_evidence_duplication(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference7', 5000, orient=ORIENT.RIGHT),
            Breakpoint('reference7', 11000, orient=ORIENT.LEFT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(35, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(11, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(64, len(ev1.flanking_pairs))

    def test_load_evidence_deletion1(self):
        # first example
        ev1 = self.genome_evidence(
            Breakpoint('reference20', 2000, orient=ORIENT.LEFT),
            Breakpoint('reference20', 6000, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(22, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(14, self.count_original_reads(ev1.split_reads[1]))

    def test_load_evidence_deletion2(self):
        # second example
        ev1 = self.genome_evidence(
            Breakpoint('referenceX', 2000, orient=ORIENT.LEFT),
            Breakpoint('referenceX', 6000, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(4, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(10, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(27, len(ev1.flanking_pairs))

    def test_load_evidence_deletion3(self):
        # third example
        ev1 = self.genome_evidence(
            Breakpoint('referenceX', 10000, orient=ORIENT.LEFT),
            Breakpoint('referenceX', 14000, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(8, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(9, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(26, len(ev1.flanking_pairs))

    def test_load_evidence_deletion4(self):
        # forth example
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 3609, orient=ORIENT.LEFT),
            Breakpoint('reference10', 3818, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(20, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(17, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(40, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion1(self):
        # first example
        ev1 = self.genome_evidence(
            Breakpoint('reference11', 6000, orient=ORIENT.LEFT),
            Breakpoint('reference11', 6003, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))

        self.assertEqual(5, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(3, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(20, len(ev1.spanning_reads))
        self.assertEqual(6, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion2(self):
        # second example
        ev1 = self.genome_evidence(
            Breakpoint('reference11', 10000, orient=ORIENT.LEFT),
            Breakpoint('reference11', 10030, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read, mate in ev1.flanking_pairs:
            print(read.query_name)

        self.assertEqual(27, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(52, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(19, len(ev1.spanning_reads))
        self.assertEqual(7, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test1(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference12', 2001, orient=ORIENT.LEFT),
            Breakpoint('reference12', 2120, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read, mate in ev1.flanking_pairs:
            print(read.query_name)

        self.assertEqual(18, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(16, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.spanning_reads))
        self.assertEqual(22, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test2(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 3609, orient=ORIENT.LEFT),
            Breakpoint('reference10', 3818, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        self.assertEqual(20, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(17, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.spanning_reads))
        self.assertEqual(40, len(set(ev1.flanking_pairs)))

    def test_load_evidence_small_deletion_test3(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 8609, orient=ORIENT.LEFT),
            Breakpoint('reference10', 8927, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(27, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(5, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.spanning_reads))
        self.assertEqual(53, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test4(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 12609, orient=ORIENT.LEFT),
            Breakpoint('reference10', 13123, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        print(self.count_original_reads(ev1.split_reads[0]))
        print(self.count_original_reads(ev1.split_reads[1]))

        self.assertEqual(33, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(6, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.spanning_reads))
        self.assertEqual(77, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test5(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 17109, orient=ORIENT.LEFT),
            Breakpoint('reference10', 17899, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        print(self.count_original_reads(ev1.split_reads[0]))
        print(self.count_original_reads(ev1.split_reads[1]))

        self.assertEqual(19, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(11, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.spanning_reads))
        self.assertEqual(48, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test6(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 22109, orient=ORIENT.LEFT),
            Breakpoint('reference10', 24330, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        print(self.count_original_reads(ev1.split_reads[0]))
        print(self.count_original_reads(ev1.split_reads[1]))

        self.assertEqual(18, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(13, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(53, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test7(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 28109, orient=ORIENT.LEFT),
            Breakpoint('reference10', 31827, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        print(self.count_original_reads(ev1.split_reads[0]))
        print(self.count_original_reads(ev1.split_reads[1]))

        self.assertEqual(39, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(13, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(49, len(ev1.flanking_pairs))

    def test_load_evidence_small_deletion_test8(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference10', 36109, orient=ORIENT.LEFT),
            Breakpoint('reference10', 42159, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        print(self.count_original_reads(ev1.split_reads[0]))
        print(self.count_original_reads(ev1.split_reads[1]))

        self.assertEqual(59, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(8, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(59, len(ev1.flanking_pairs))


    @unittest.skip('skip because too complex')
    def test_load_evidence_complex_deletion(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference12', 6001, orient=ORIENT.LEFT),
            Breakpoint('reference12', 6016, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        print(self.count_original_reads(ev1.split_reads[0]))
        print(self.count_original_reads(ev1.split_reads[1]))

        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(76, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(83, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(1, len(ev1.spanning_reads))
        self.assertEqual(2, len(ev1.flanking_pairs))

    @unittest.skip('skip because high coverage')
    def test_load_evidence_small_insertion(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference1', 2000, orient=ORIENT.LEFT),
            Breakpoint('reference1', 2001, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(17, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(17, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(48, len(ev1.spanning_reads))
        self.assertEqual(4, len(ev1.flanking_pairs))

    @unittest.skip('skip because too high coverage')
    def test_load_evidence_small_insertion_high_coverage(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference9', 2000, orient=ORIENT.LEFT),
            Breakpoint('reference9', 2001, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(37, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(52, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(37, len(ev1.spanning_reads))
        self.assertEqual(9, len(ev1.flanking_pairs))

        ev1 = self.genome_evidence(
            Breakpoint('reference16', 2000, orient=ORIENT.LEFT),
            Breakpoint('reference16', 2001, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(27, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(52, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(19, len(ev1.spanning_reads))
        self.assertEqual(9, len(ev1.flanking_pairs))

    def test_load_evidence_small_duplication(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference12', 10000, orient=ORIENT.RIGHT),
            Breakpoint('reference12', 10021, orient=ORIENT.LEFT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(29, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(51, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.spanning_reads))
        self.assertEqual(0, len(ev1.flanking_pairs))

        #Example 2
        ev1 = self.genome_evidence(
            Breakpoint('reference17', 1974, orient=ORIENT.RIGHT),
            Breakpoint('reference17', 2020, orient=ORIENT.LEFT),
            opposing_strands=False
        )
        ev1.load_evidence()

        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs), len(ev1.spanning_reads))
        print(len(ev1.spanning_reads))
        for read in sorted(ev1.spanning_reads, key=lambda x: x.query_name):
            print(read.query_name)

        self.assertEqual(25, self.count_original_reads(ev1.split_reads[0]))
        self.assertEqual(56, self.count_original_reads(ev1.split_reads[1]))
        self.assertEqual(3, len(ev1.spanning_reads))
        self.assertEqual(0, len(ev1.flanking_pairs))

    def test_load_evidence_low_qual_deletion(self):
        ev1 = self.genome_evidence(
            Breakpoint('reference19', 4847, 4847, orient=ORIENT.LEFT),
            Breakpoint('reference19', 5219, 5219, orient=ORIENT.RIGHT),
            opposing_strands=False
        )
        ev1.load_evidence()
        print(len(ev1.spanning_reads))
        print(len(ev1.split_reads[0]), len(ev1.flanking_pairs))
        self.assertEqual(0, len(ev1.split_reads[0]))
        self.assertEqual(0, len(ev1.split_reads[1]))
        self.assertEqual(0, len(ev1.flanking_pairs))



class TestEvidenceGathering(unittest.TestCase):

    def setUp(self):
        # test loading of evidence for event found on reference3 1114 2187
        self.ev1 = GenomeEvidence(
            Breakpoint('reference3', 1114, orient=ORIENT.RIGHT),
            Breakpoint('reference3', 2187, orient=ORIENT.RIGHT),
            BAM_CACHE, REFERENCE_GENOME,
            opposing_strands=True,
            read_length=125,
            stdev_fragment_size=100,
            median_fragment_size=380,
            stdev_count_abnormal=3,
            min_flanking_pairs_resolution=3,
            assembly_min_nc_edge_weight=3,
            assembly_min_edge_weight=0
        )

    def test_collect_split_read(self):
        ev1_sr = MockRead(query_name='HISEQX1_11:3:1105:15351:25130:split',
                          reference_id=1, cigar=[(4, 68), (7, 82)], reference_start=1114,
                          reference_end=1154, query_alignment_start=110,
                          query_sequence='TCGTGAGTGGCAGGTGCCATCGTGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTG',
                          query_alignment_end=150, flag=113,
                          next_reference_id=1, next_reference_start=2341)
        self.ev1.collect_split_read(ev1_sr, True)
        self.assertEqual(ev1_sr, list(self.ev1.split_reads[0])[0])

    def test_collect_split_read_failure(self):
        # wrong cigar string
        ev1_sr = MockRead(query_name='HISEQX1_11:4:1203:3062:55280:split',
                          reference_id=1, cigar=[(7, 110), (7, 40)], reference_start=1114,
                          reference_end=1154, query_alignment_start=110,
                          query_sequence='CTGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCGTGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATG',
                          query_alignment_end=150, flag=371,
                          next_reference_id=1, next_reference_start=2550)
        self.assertFalse(self.ev1.collect_split_read(ev1_sr, True))

    def test_collect_flanking_pair(self):
        self.ev1.collect_flanking_pair(
            MockRead(
                reference_id=1, reference_start=2214, reference_end=2364, is_reverse=True,
                next_reference_id=1, next_reference_start=1120, mate_is_reverse=True
            ),
            MockRead(
                reference_id=1, reference_start=1120, reference_end=2364, is_reverse=True,
                next_reference_id=1, next_reference_start=1120, mate_is_reverse=True,
                is_read1=False
            )
        )
        self.assertEqual(1, len(self.ev1.flanking_pairs))

    def test_collect_flanking_pair_not_overlapping_evidence_window(self):
        # first read in pair does not overlap the first evidence window
        # therefore this should return False and not add to the flanking_pairs
        pair = mock_read_pair(
            MockRead(reference_id=1, reference_start=1903, reference_end=2053, is_reverse=True),
            MockRead(reference_id=1, reference_start=2052, reference_end=2053, is_reverse=True)
        )
        self.assertFalse(self.ev1.collect_flanking_pair(*pair))
        self.assertEqual(0, len(self.ev1.flanking_pairs))

#    @unittest.skip("demonstrating skipping")
    def test_load_evidence(self):
        print(self.ev1)
        self.ev1.load_evidence()
        print(self.ev1.spanning_reads)
        self.assertEqual(
            2,
            len([r for r in self.ev1.split_reads[0] if not r.has_tag(PYSAM_READ_FLAGS.TARGETED_ALIGNMENT)]))
        self.assertEqual(7, len(self.ev1.flanking_pairs))
        self.assertEqual(
            2,
            len([r for r in self.ev1.split_reads[1] if not r.has_tag(PYSAM_READ_FLAGS.TARGETED_ALIGNMENT)]))

#    @unittest.skip("demonstrating skipping")
    def test_assemble_split_reads(self):
        sr1 = MockRead(query_name='HISEQX1_11:3:1105:15351:25130:split',
                       query_sequence='TCGTGAGTGGCAGGTGCCATCGTGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTG',
                       flag=113)
        sr2 = MockRead(query_sequence='GTCGTGAGTGGCAGGTGCCATCGTGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTT', flag=121)
        sr3 = MockRead(query_sequence='TCGTGAGTGGCAGGTGCCATCGTGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTG', flag=113)
        sr5 = MockRead(query_sequence='CTGAGCATGAAAGCCCTGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAAT', flag=113)
        sr6 = MockRead(query_sequence='GCATGAAAGCCCTGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAA', flag=113)
        sr7 = MockRead(query_sequence='TGAAAGCCCTGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATA', flag=113)
        sr8 = MockRead(query_sequence='CCCTGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTA', flag=113)
        sr9 = MockRead(query_sequence='TGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGC', flag=113)
        sr10 = MockRead(query_sequence='ACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTG', flag=113)
        sr11 = MockRead(query_sequence='TTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACT', flag=113)
        sr12 = MockRead(query_sequence='GATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAG', flag=113)
        sr13 = MockRead(query_sequence='TTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATG', flag=113)
        sr14 = MockRead(query_sequence='TTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCT', flag=113)
        sr15 = MockRead(query_sequence='GTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACA', flag=113)
        sr16 = MockRead(query_sequence='CCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATAT', flag=113)
        sr17 = MockRead(query_sequence='CGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGG', flag=113)
        sr18 = MockRead(query_sequence='GGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAA', flag=113)
        sr19 = MockRead(query_sequence='TGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCA', flag=113)
        sr20 = MockRead(query_sequence='CATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTT', flag=113)
        sr21 = MockRead(query_sequence='TCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTTTCATTT', flag=113)
        sr22 = MockRead(query_sequence='TTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTTTCATTTCTG', flag=113)
        sr23 = MockRead(query_sequence='TGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTTTCATTTCTGTAT', flag=113)
        sr24 = MockRead(query_sequence='CTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTTTCATTTCTGTATGTT', flag=113)
        sr25 = MockRead(query_sequence='AGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTTTCATTTCTGTATGTTAAT', flag=113)
        self.ev1.split_reads = ([], [sr1, sr3, sr7, sr9, sr12, sr15, sr19, sr24])  # subset needed to make a contig
#        self.ev1.split_reads=([],[sr1,sr3,sr5,sr6,sr7,sr8,sr9,sr10,sr11,sr12,sr13,sr14,sr15,sr16,sr17,sr18,sr19,sr20,sr21,sr22,sr23,sr24]) #full set of reads produces different contig from subset.
        # full contig with more read support should be
        # CTGAGCATGAAAGCCCTGTAAACACAGAATTTGGATTCTTTCCTGTTTGGTTCCTGGTCGTGAGTGGCAGGTGCCATCATGTTTCATTCTGCCTGAGAGCAGTCTACCTAAATATATAGCTCTGCTCACAGTTTCCCTGCAATGCATAATTAAAATAGCACTATGCAGTTGCTTACACTTCAGATAATGGCTTCCTACATATTGTTGGTTATGAAATTTCAGGGTTTTCATTTCTGTATGTTAAT
        self.ev1.half_mapped = ([], [sr2])
        self.ev1.assemble_contig()
        print(self.ev1.contigs)
        self.assertEqual(
            'CAACAATATGTAGGAAGCCATTATCTGAAGTGTAAGCAACTGCATAGTGCTATTTTAATTATGCATTGCAGGGAAACTGTGAGCAGAGCTATATATTTAGGTAGACTGCTCTCAGGCAGAATGAAACATGATGGCACCTGCCACTCACGACCAGGAACCAAACAGGAAAGAATC', self.ev1.contigs[0].seq)


class MockEvidence:

    def __init__(self, ref=None):
        self.HUMAN_REFERENCE_GENOME = ref



if __name__ == "__main__":
    unittest.main()