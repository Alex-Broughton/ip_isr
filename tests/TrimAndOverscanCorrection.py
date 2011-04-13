#!/usr/bin/env python

# 
# LSST Data Management System
# Copyright 2008, 2009, 2010 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.
#

import os

import unittest
import lsst.utils.tests as tests

import eups
import lsst.afw.detection as afwDetection
import lsst.afw.image as afwImage
import lsst.afw.geom as afwGeom
import lsst.pex.policy as pexPolicy
import lsst.ip.isr as ipIsr
import lsst.pex.logging as logging

import lsst.afw.display.ds9 as ds9

Verbosity = 4
logging.Trace_setVerbosity('lsst.ip.isr', Verbosity)

isrDir     = eups.productDir('ip_isr')


# Policy file
InputIsrPolicy = os.path.join(isrDir, 'pipeline', 'isrPolicy.paf')

class IsrTestCases(unittest.TestCase):
    
    def setUp(self):
        self.policy = pexPolicy.Policy.createPolicy(InputIsrPolicy)

    def tearDown(self):
        del self.policy

    def testOverscanCorrectionY(self):
	bbox = afwGeom.Box2I(afwGeom.Point2I(0,0),
			    afwGeom.Point2I(9,12))
        mi = afwImage.MaskedImageF(bbox)
        mi.set(10, 0x0, 1)

        # these should be functionally equivalent
        bbox     = afwGeom.Box2I(afwGeom.Point2I(0,10),
                                 afwGeom.Point2I(9,12))
        biassec  = '[1:10,11:13]'
        overscan = afwImage.MaskedImageF(mi, bbox, afwImage.PARENT)
        overscan.set(2, 0x0, 1)
        
        overscanKeyword = self.policy.getString('overscanPolicy.overscanKeyword')
        fitType = self.policy.getPolicy('overscanPolicy').getString('overscanFitType')

        exposure = afwImage.ExposureF(mi, afwImage.Wcs())
        metadata = exposure.getMetadata()
        metadata.setString(overscanKeyword, biassec)

        ipIsr.overscanCorrection(exposure, ipIsr.BBoxFromDatasec(biassec),
                fitType, overscanKeyword)

        height        = mi.getHeight()
        width         = mi.getWidth()
        for j in range(height):
            for i in range(width):
                if j >= 10:
                    self.assertEqual(mi.getImage().get(i,j), 0)
                else:
                    self.assertEqual(mi.getImage().get(i,j), 8)

    def testOverscanCorrectionX(self):
	bbox = afwGeom.Box2I(afwGeom.Point2I(0,0),
			    afwGeom.Point2I(12,9))
        mi = afwImage.MaskedImageF(bbox)
        mi.set(10, 0x0, 1)

        # these should be functionally equivalent
        bbox     = afwGeom.Box2I(afwGeom.Point2I(10,0),
                                 afwGeom.Point2I(12,9))
        biassec  = '[11:13,1:10]'
        overscan = afwImage.MaskedImageF(mi, bbox, afwImage.PARENT)
        overscan.set(2, 0x0, 1)
        
        overscanKeyword = self.policy.getString('overscanPolicy.overscanKeyword')
        fitType = self.policy.getPolicy('overscanPolicy').getString('overscanFitType')
        exposure = afwImage.ExposureF(mi, afwImage.Wcs())
        metadata = exposure.getMetadata()
        metadata.setString(overscanKeyword, biassec)

        ipIsr.overscanCorrection(exposure, ipIsr.BBoxFromDatasec(biassec),
                fitType, overscanKeyword)

        height        = mi.getHeight()
        width         = mi.getWidth()
        for j in range(height):
            for i in range(width):
                if i >= 10:
                    self.assertEqual(mi.getImage().get(i,j), 0)
                else:
                    self.assertEqual(mi.getImage().get(i,j), 8)

    def testTrimY0(self):
	bbox = afwGeom.Box2I(afwGeom.Point2I(0,0), afwGeom.Point2I(9,12))
        mi = afwImage.MaskedImageF(bbox)
        mi.set(10, 0x0, 1)

        # these should be functionally equivalent
        bbox     = afwGeom.Box2I(afwGeom.Point2I(0,10),
                                 afwGeom.Point2I(9,12))
        trimsec  = '[1:10,1:10]'
        ampBBox = ipIsr.BBoxFromDatasec(trimsec)
        ampBBox.shift(afwGeom.Extent2I(-ampBBox.getMin().getX(),
            -ampBBox.getMin().getY()))

        trimsecKeyword = self.policy.getString('trimPolicy.trimsecKeyword')
        exposure = afwImage.ExposureF(mi, afwImage.Wcs())
        metadata = exposure.getMetadata()
        metadata.setString(trimsecKeyword, trimsec)

        exposure2 = ipIsr.trimNew(exposure, 
                ampBBox, trimsecKeyword = trimsecKeyword)
        mi2       = exposure2.getMaskedImage()

        height        = mi2.getHeight()
        width         = mi2.getWidth()
        self.assertEqual(height, 10)
        self.assertEqual(width,  10)
        for j in range(height):
            for i in range(width):
                self.assertEqual(mi2.getImage().get(i,j), 10)

        xyOrigin = mi2.getXY0()
        self.assertEqual(xyOrigin[0], 0)
        self.assertEqual(xyOrigin[1], 0)

    def testTrimY1(self):
	bbox = afwGeom.Box2I(afwGeom.Point2I(0,0), afwGeom.Point2I(9,12))
        mi = afwImage.MaskedImageF(bbox)
        mi.set(10, 0x0, 1)

        # these should be functionally equivalent
        bbox     = afwGeom.Box2I(afwGeom.Point2I(0,3),
                                 afwGeom.Point2I(9,12))
        trimsec  = '[1:10,4:13]'
        ampBBox = ipIsr.BBoxFromDatasec(trimsec)
        ampBBox.shift(afwGeom.Extent2I(-ampBBox.getMin().getX(),
            -ampBBox.getMin().getY()))
        
        trimsecKeyword = self.policy.getString('trimPolicy.trimsecKeyword')
        exposure = afwImage.ExposureF(mi, afwImage.Wcs())
        metadata = exposure.getMetadata()
        metadata.setString(trimsecKeyword, trimsec)

        exposure2 = ipIsr.trimNew(exposure,
                ampBBox, trimsecKeyword=trimsecKeyword)
        mi2       = exposure2.getMaskedImage()

        height        = mi2.getHeight()
        width         = mi2.getWidth()
        self.assertEqual(height, 10)
        self.assertEqual(width,  10)
        for j in range(height):
            for i in range(width):
                self.assertEqual(mi2.getImage().get(i,j), 10)

        xyOrigin = mi2.getXY0()
        self.assertEqual(xyOrigin[0], 0)
        self.assertEqual(xyOrigin[1], 0)

    def testTrimX0(self):
	bbox = afwGeom.Box2I(afwGeom.Point2I(0,0), afwGeom.Point2I(12,9))
        mi = afwImage.MaskedImageF(bbox)
        mi.set(10, 0x0, 1)

        # these should be functionally equivalent
        bbox     = afwGeom.Box2I(afwGeom.Point2I(10,0),
                                 afwGeom.Point2I(12,9))
        trimsec  = '[1:10,1:10]'
        ampBBox = ipIsr.BBoxFromDatasec(trimsec)
        ampBBox.shift(afwGeom.Extent2I(-ampBBox.getMin().getX(),
            -ampBBox.getMin().getY()))
        
        trimsecKeyword = self.policy.getString('trimPolicy.trimsecKeyword')
        exposure = afwImage.ExposureF(mi, afwImage.Wcs())
        metadata = exposure.getMetadata()
        metadata.setString(trimsecKeyword, trimsec)

        exposure2 = ipIsr.trimNew(exposure,
                ampBBox, trimsecKeyword=trimsecKeyword)
        mi2       = exposure2.getMaskedImage()

        height        = mi2.getHeight()
        width         = mi2.getWidth()
        self.assertEqual(height, 10)
        self.assertEqual(width,  10)
        for j in range(height):
            for i in range(width):
                self.assertEqual(mi2.getImage().get(i,j), 10)

        xyOrigin = mi2.getXY0()
        self.assertEqual(xyOrigin[0], 0)
        self.assertEqual(xyOrigin[1], 0)

    def testTrimX1(self):
	bbox = afwGeom.Box2I(afwGeom.Point2I(0,0), afwGeom.Point2I(12,9))
        mi = afwImage.MaskedImageF(bbox)
        mi.set(10, 0x0, 1)

        # these should be functionally equivalent
        bbox     = afwGeom.Box2I(afwGeom.Point2I(0,0),
                                 afwGeom.Point2I(2,9))
        trimsec  = '[4:13,1:10]'
        ampBBox = ipIsr.BBoxFromDatasec(trimsec)
        ampBBox.shift(afwGeom.Extent2I(-ampBBox.getMin().getX(),
            -ampBBox.getMin().getY()))
        
        trimsecKeyword = self.policy.getString('trimPolicy.trimsecKeyword')
        exposure = afwImage.ExposureF(mi, afwImage.Wcs())
        metadata = exposure.getMetadata()
        metadata.setString(trimsecKeyword, trimsec)

        exposure2 = ipIsr.trimNew(exposure,
                ampBBox, trimsecKeyword = trimsecKeyword)
        mi2       = exposure2.getMaskedImage()

        height        = mi2.getHeight()
        width         = mi2.getWidth()
        self.assertEqual(height, 10)
        self.assertEqual(width,  10)
        for j in range(height):
            for i in range(width):
                self.assertEqual(mi2.getImage().get(i,j), 10)

        xyOrigin = mi2.getXY0()
        self.assertEqual(xyOrigin[0], 0)
        self.assertEqual(xyOrigin[1], 0)
#####
        
def suite():
    """Returns a suite containing all the test cases in this module."""
    tests.init()

    suites = []
    suites += unittest.makeSuite(IsrTestCases)
    suites += unittest.makeSuite(tests.MemoryTestCase)
    return unittest.TestSuite(suites)

def run(exit=False):
    """Run the tests"""
    tests.run(suite(), exit)

if __name__ == "__main__":
    run(True)
