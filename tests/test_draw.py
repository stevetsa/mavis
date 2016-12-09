import unittest
from structural_variant.draw import Diagram, HEX_BLACK, HEX_WHITE
from structural_variant.annotate import Gene, Transcript, Domain, Annotation
from svgwrite import Drawing
from structural_variant.constants import STRAND, ORIENT
from structural_variant.breakpoint import Breakpoint, BreakpointPair
from structural_variant.interval import Interval


class TestDraw(unittest.TestCase):
    def setUp(self):
        self.canvas = Drawing(height=100, width=1000)
    
    def test__generate_interval_mapping(self):
        x = Interval(150, 1000)
        y = Interval(1500, 1950)
        z = Interval(5000, 7500)
        temp = Diagram._generate_interval_mapping(
            [x, y, z], target_width=960, ratio=5, min_width=22, buffer=200)
        self.assertEqual(7, len(temp.keys()))
        expt = [
            (Interval(1, 149), Interval(1, 27)),
            (Interval(150, 1000), Interval(28, 198)),
            (Interval(1001, 1499), Interval(199, 237)),
            (Interval(1500, 1950), Interval(238, 338)),
            (Interval(1951, 4999), Interval(339, 467)),
            (Interval(5000, 7500), Interval(468, 928)),
            (Interval(7501, 7700), Interval(929, 960))
        ]
        self.assertEqual(expt, sorted(temp.items()))


    def test__generate_gene_mapping(self):
        d = Diagram()
        a = Gene('1', 1000, 2000)
        b = Gene('1', 5000, 7000)
        c = Gene('1', 1500, 2500)
        genes = [a, b, c]
        """return self._generate_interval_mapping(
            target_width,
            genes,
            self.GENE_INTERGENIC_RATIO,
            self.MIN_WIDTH + self.GENE_ARROW_WIDTH,
            buffer=self.GENE_MIN_BUFFER
        )
        with self.assertRaises(AttributeError):
            m = d._generate_gene_mapping(100, genes)
        m = d._generate_gene_mapping(500, genes)
        u = Interval.union(*m.values())
        self.assertLessEqual(1, u.start)
        self.assertGreaterEqual(500, u.end)"""

    def test__split_intervals_into_tracks(self):
        # ----======---------
        # ------======--------
        # -----===============
        t = Diagram._split_intervals_into_tracks(
            [(1, 3), (3, 7), (2, 2), (4, 5), (3, 10)]
        )
        self.assertEqual(3, len(t))
        self.assertEqual([(1, 3), (4, 5)], t[0])
        self.assertEqual([(2, 2), (3, 7)], t[1])
        self.assertEqual([(3, 10)], t[2])

    def test_draw_genes(self):

        x = Gene('1', 1000, 2000, strand=STRAND.POS)
        y = Gene('1', 5000, 7000, strand=STRAND.NEG)
        z = Gene('1', 1500, 2500, strand=STRAND.POS)

        d = Diagram()
        breakpoints = [
            Breakpoint('1', 1100, 1200, orient=ORIENT.RIGHT)
        ]
        g = d.draw_genes(
            self.canvas, [x, y, z], 500, breakpoints, {x: d.GENE1_COLOR, y: d.GENE2_COLOR_SELECTED, z: d.GENE2_COLOR})

        # test the class structure
        self.assertEqual(5, len(g.elements))
        self.assertEqual('scaffold', g.elements[0].attribs.get('class', ''))
        for i in range(1, 4):
            self.assertEqual('gene', g.elements[i].attribs.get('class', ''))
        self.assertEqual('breakpoint', g.elements[4].attribs.get('class', ''))
        self.assertEqual(
            d.TRACK_HEIGHT * 2 + d.PADDING + d.BREAKPOINT_BOTTOM_MARGIN + d.BREAKPOINT_TOP_MARGIN,
            g.height
        )
        self.canvas.add(g)
        self.canvas.saveas('test1.svg')
        self.assertEqual(len(g.labels), 4)
        self.assertEqual(x, g.labels['G1'])
        self.assertEqual(z, g.labels['G2'])
        self.assertEqual(y, g.labels['G3'])
        self.assertEqual(breakpoints[0], g.labels['B1'])

    def test_draw_transcript(self):
        d = Diagram()
        # domains = [Domain()]
        d1 = Domain('first', [(55, 61), (71, 73)])
        d2 = Domain('second', [(10, 20), (30, 34)])

        t = Transcript(
            gene=None,
            cds_start=50,
            cds_end=249,
            exons=[(1, 99), (200, 299), (400, 499)],
            strand=STRAND.NEG,
            domains=[d2, d1]
        )
        b = Breakpoint('1', 350, 410, orient=ORIENT.LEFT)
        g = d.draw_transcript(
            self.canvas, t, 500,
            exon_color=d.EXON2_COLOR,
            utr_color=d.EXON2_UTR_COLOR,
            abrogated_splice_sites=[200, 299],
            breakpoints=[b]
        )
        self.canvas.add(g)
        self.canvas.saveas('test2.svg')
        self.assertEqual(8, len(g.elements))
        self.assertEqual('splicing', g.elements[0].attribs.get('class', ''))
        self.assertEqual('scaffold', g.elements[1].attribs.get('class', ''))
        for i in range(2, 5):
            self.assertEqual('exon', g.elements[i].attribs.get('class', ''))
        for i in [5, 6]:
            self.assertEqual('domain', g.elements[i].attribs.get('class', ''))
        self.assertEqual(d1, g.labels['D1'])
        self.assertEqual(d2, g.labels['D2'])
        self.assertEqual('breakpoint', g.elements[7].attribs.get('class', ''))
        self.assertEqual(
            d.TRACK_HEIGHT / 2 
            + max(d.TRACK_HEIGHT / 2, d.SPLICE_HEIGHT)
            + 2 * d.PADDING + d.DOMAIN_TRACK_HEIGHT * 2
            + d.BREAKPOINT_TOP_MARGIN
            + d.BREAKPOINT_BOTTOM_MARGIN,
            g.height)

    def test_dynamic_label_color(self):
        self.assertEqual(HEX_WHITE, Diagram.dynamic_label_color(HEX_BLACK))
        self.assertEqual(HEX_BLACK, Diagram.dynamic_label_color(HEX_WHITE))

    def test_draw_legend(self):
        d = Diagram()
        swatches = [
            ('#000000', 'black'),
            ('#FF0000', 'red'),
            ('#0000FF', 'blue'),
            ('#00FF00', 'green'),
            ('#FFFF00', 'yellow')
        ]
        g = d.draw_legend(self.canvas, swatches)
        self.canvas.add(g)
        self.canvas.saveas('test_legend.svg')
        
        self.assertEqual('legend', g.attribs.get('class', ''))
        self.assertEqual(
            d.LEGEND_SWATCH_SIZE * len(swatches) + d.PADDING * (len(swatches) - 1 + 2),
            g.height
        )
        self.assertEqual(6, len(g.elements))
        self.assertEqual(
            6 * d.LEGEND_FONT_SIZE * d.FONT_WIDTH_HEIGHT_RATIO + d.PADDING * 3 + d.LEGEND_SWATCH_SIZE,
            g.width
        )
    
    def test_draw_layout_single_transcript(self):
        d = Diagram()
        d1 = Domain('first', [(55, 61), (71, 73)])
        d2 = Domain('second', [(10, 20), (30, 34)])
        g1 = Gene('1', 150, 1000, strand=STRAND.POS)
        t = Transcript(
            gene=g1,
            cds_start=50,
            cds_end=249,
            exons=[(200, 299), (400, 499), (700, 899)],
            domains=[d2, d1]
        )
        b1 = Breakpoint('1', 350, orient=ORIENT.LEFT)
        b2 = Breakpoint('1', 600, orient=ORIENT.RIGHT)
        bpp = BreakpointPair(b1, b2, opposing_strands=False)
        ann = Annotation(bpp, transcript1=t, transcript2=t)
        ann.add_gene(Gene('1', 1500, 1950, strand=STRAND.POS))
        canvas = d.draw(ann)
        #canvas.saveas('test.svg')
        #self.assertEqual(4, len(canvas.elements))  # defs counts as element
        

    def test_draw_layout_single_genomic(self):
        d = Diagram()
        d1 = Domain('first', [(55, 61), (71, 73)])
        d2 = Domain('second', [(10, 20), (30, 34)])
        g1 = Gene('1', 150, 1000, strand=STRAND.POS)
        g2 = Gene('1', 5000, 7500, strand=STRAND.NEG)
        t1 = Transcript(
            gene=g1,
            cds_start=50,
            cds_end=249,
            exons=[(200, 299), (400, 499), (700, 899)],
            domains=[d2, d1]
        )
        t2 = Transcript(
            gene=g2,
            cds_start=20,
            cds_end=500,
            exons=[(5100, 5299), (5800, 6199), (6500, 6549), (6700, 6799)]
        )
        b1 = Breakpoint('1', 350, orient=ORIENT.LEFT)
        b2 = Breakpoint('1', 6500, 6650, orient=ORIENT.RIGHT)
        bpp = BreakpointPair(b1, b2, opposing_strands=False)
        ann = Annotation(bpp, transcript1=t1, transcript2=t2)
        ann.add_gene(Gene('1', 1500, 1950, strand=STRAND.POS))
        ann.add_gene(Gene('1', 3000, 3980, strand=STRAND.POS))
        ann.add_gene(Gene('1', 3700, 4400, strand=STRAND.NEG))
        canvas = d.draw(ann)
        canvas.saveas('test.svg')
        #self.assertEqual(5, len(canvas.elements))  # defs counts as element

    def test_draw_layout_translocation(self):
        pass
    
    def test_draw_layout_intergenic_breakpoint(self):
        pass