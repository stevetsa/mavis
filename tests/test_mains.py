from tempfile import mkdtemp
import unittest
import shutil
import pysam
import re
import os
import glob
from . import REFERENCE_GENOME_FILE, FULL_REFERENCE_ANNOTATIONS_FILE_JSON, TEMPLATE_METADATA_FILE
from . import FULL_BAM_INPUT, TRANSCRIPTOME_BAM_INPUT, FULL_BASE_EVENTS, REFERENCE_GENOME_FILE_2BIT
from . import RUN_FULL
from mavis.annotate.file_io import load_templates, load_reference_genes, load_reference_genome
import mavis.cluster
import mavis.validate
import mavis.annotate

annotations = None
reference_genome = None
template_metadata = None
trans_bam_fh = None
genome_bam_fh = None
masking = {}  # do not mask


def setUpModule():
    global annotations, reference_genome, template_metadata, genome_bam_fh, trans_bam_fh, masking
    print('setup start')
    annotations = load_reference_genes(FULL_REFERENCE_ANNOTATIONS_FILE_JSON)
    reference_genome = load_reference_genome(REFERENCE_GENOME_FILE)
    template_metadata = load_templates(TEMPLATE_METADATA_FILE)
    genome_bam_fh = pysam.AlignmentFile(FULL_BAM_INPUT)
    trans_bam_fh = pysam.AlignmentFile(TRANSCRIPTOME_BAM_INPUT)
    print('setup loading is complete')


def tearDownModule():
    trans_bam_fh.close()
    genome_bam_fh.close()


@unittest.skipIf(not RUN_FULL, 'slower tests will not be run unless the environment variable RUN_FULL is given')
class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.output = mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.output)
    
    def test_mains(self):
        # test the clustering
        cluster_files = mavis.cluster.main(
            [FULL_BASE_EVENTS], self.output, False, 'mock-A36971', 'genome',
            masking=masking, cluster_clique_size=15, cluster_radius=20,
            uninformative_filter=True, max_proximity=5000,
            annotations=annotations, min_clusters_per_file=5, max_files=1
        )
        self.assertGreaterEqual(100, len(cluster_files))
        self.assertLessEqual(1, len(cluster_files))
        # next test the validate runs without errors
        mavis.validate.main(
            cluster_files[0], self.output, genome_bam_fh, False, 'mock-A36971', 'genome',
            median_fragment_size=427, stdev_fragment_size=106, read_length=150,
            reference_genome=reference_genome, annotations=annotations, masking=masking,
            blat_2bit_reference=REFERENCE_GENOME_FILE_2BIT, samtools_version=None
        )
        prefix = re.sub('\.tab$', '', cluster_files[0])
        for suffix in [
            '.validation-passed.tab', 
            '.validation-failed.tab', 
            '.raw_evidence.bam', 
            '.raw_evidence.sorted.bam',
            '.raw_evidence.sorted.bam.bai',
            '.contigs.sorted.bam',
            '.contigs.sorted.bam.bai',
            '.contigs.bam',
            '.igv.batch'
        ]:
            self.assertTrue(os.path.exists(prefix + suffix))
        
        # test the annotation
        mavis.annotate.main(
            [prefix + '.validation-passed.tab'], self.output,
            reference_genome, annotations, template_metadata,
            min_domain_mapping_match=0.95, min_orf_size=300, max_orf_cap=3,
        )
        self.assertTrue(os.path.exists(os.path.join(self.output, 'annotations.tab')))
        self.assertTrue(os.path.exists(os.path.join(self.output, 'annotations.fusion-cdna.fa')))
        drawings_dir = os.path.join(self.output, 'drawings')
        self.assertTrue(os.path.exists(drawings_dir))
        self.assertLessEqual(1, len(glob.glob(os.path.join(drawings_dir, '*.svg'))))
        self.assertLessEqual(1, len(glob.glob(os.path.join(drawings_dir, '*.legend.json'))))

