# This file is part of ip_isr.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Brighter Fatter Kernel calibration definition."""


__all__ = ['BrighterFatterKernel']


import numpy as np
from astropy.table import Table
import lsst.afw.math as afwMath
from . import IsrCalib


class BrighterFatterKernel(IsrCalib):
    """Calibration of brighter-fatter kernels for an instrument.

    ampKernels are the kernels for each amplifier in a detector, as
    generated by having ``level == 'AMP'``.

    detectorKernel is the kernel generated for a detector as a
    whole, as generated by having ``level == 'DETECTOR'``.

    makeDetectorKernelFromAmpwiseKernels is a method to generate the
    kernel for a detector, constructed by averaging together the
    ampwise kernels in the detector.  The existing application code is
    only defined for kernels with ``level == 'DETECTOR'``, so this method
    is used if the supplied kernel was built with ``level == 'AMP'``.

    Parameters
    ----------
    camera : `lsst.afw.cameraGeom.Camera`
        Camera describing detector geometry.
    level : `str`
        Level the kernels will be generated for.
    log : `logging.Logger`, optional
        Log to write messages to.
    **kwargs :
        Parameters to pass to parent constructor.

    Notes
    -----
    Version 1.1 adds the `expIdMask` property, and substitutes
    `means` and `variances` for `rawMeans` and `rawVariances`
    from the PTC dataset.

    expIdMask : `dict`, [`str`,`numpy.ndarray`]
        Dictionary keyed by amp names containing the mask produced after
        outlier rejection.
    rawMeans : `dict`, [`str`, `numpy.ndarray`]
        Dictionary keyed by amp names containing the unmasked average of the
        means of the exposures in each flat pair.
    rawVariances : `dict`, [`str`, `numpy.ndarray`]
        Dictionary keyed by amp names containing the variance of the
        difference image of the exposures in each flat pair.
        Corresponds to rawVars of PTC.
    rawXcorrs : `dict`, [`str`, `numpy.ndarray`]
        Dictionary keyed by amp names containing an array of measured
        covariances per mean flux.
        Corresponds to covariances of PTC.
    badAmps : `list`
        List of bad amplifiers names.
    shape : `tuple`
        Tuple of the shape of the BFK kernels.
    gain : `dict`, [`str`,`float`]
        Dictionary keyed by amp names containing the fitted gains.
    noise : `dict`, [`str`,`float`]
        Dictionary keyed by amp names containing the fitted noise.
    meanXcorrs : `dict`, [`str`,`numpy.ndarray`]
        Dictionary keyed by amp names containing the averaged
        cross-correlations.
    valid : `dict`, [`str`,`bool`]
        Dictionary keyed by amp names containing validity of data.
    ampKernels : `dict`, [`str`, `numpy.ndarray`]
        Dictionary keyed by amp names containing the BF kernels.
    detKernels : `dict`
        Dictionary keyed by detector names containing the BF kernels.
    """
    _OBSTYPE = 'bfk'
    _SCHEMA = 'Brighter-fatter kernel'
    _VERSION = 1.1

    def __init__(self, camera=None, level=None, **kwargs):
        self.level = level

        # Things inherited from the PTC
        self.expIdMask = dict()
        self.rawMeans = dict()
        self.rawVariances = dict()
        self.rawXcorrs = dict()
        self.badAmps = list()
        self.shape = (17, 17)
        self.gain = dict()
        self.noise = dict()

        # Things calculated from the PTC
        self.meanXcorrs = dict()
        self.valid = dict()

        # Things that are used downstream
        self.ampKernels = dict()
        self.detKernels = dict()

        super().__init__(**kwargs)

        if camera:
            self.initFromCamera(camera, detectorId=kwargs.get('detectorId', None))

        self.requiredAttributes.update(['level', 'expIdMask', 'rawMeans', 'rawVariances', 'rawXcorrs',
                                        'badAmps', 'gain', 'noise', 'meanXcorrs', 'valid',
                                        'ampKernels', 'detKernels'])

    def updateMetadata(self, setDate=False, **kwargs):
        """Update calibration metadata.

        This calls the base class's method after ensuring the required
        calibration keywords will be saved.

        Parameters
        ----------
        setDate : `bool`, optional
            Update the CALIBDATE fields in the metadata to the current
            time. Defaults to False.
        kwargs :
            Other keyword parameters to set in the metadata.
        """
        kwargs['LEVEL'] = self.level
        kwargs['KERNEL_DX'] = self.shape[0]
        kwargs['KERNEL_DY'] = self.shape[1]

        super().updateMetadata(setDate=setDate, **kwargs)

    def initFromCamera(self, camera, detectorId=None):
        """Initialize kernel structure from camera.

        Parameters
        ----------
        camera : `lsst.afw.cameraGeom.Camera`
            Camera to use to define geometry.
        detectorId : `int`, optional
            Index of the detector to generate.

        Returns
        -------
        calib : `lsst.ip.isr.BrighterFatterKernel`
            The initialized calibration.

        Raises
        ------
        RuntimeError
            Raised if no detectorId is supplied for a calibration with
            ``level='AMP'``.
        """
        self._instrument = camera.getName()

        if detectorId is not None:
            detector = camera[detectorId]
            self._detectorId = detectorId
            self._detectorName = detector.getName()
            self._detectorSerial = detector.getSerial()

        if self.level == 'AMP':
            if detectorId is None:
                raise RuntimeError("A detectorId must be supplied if level='AMP'.")

            self.badAmps = []

            for amp in detector:
                ampName = amp.getName()
                self.expIdMask[ampName] = []
                self.rawMeans[ampName] = []
                self.rawVariances[ampName] = []
                self.rawXcorrs[ampName] = []
                self.gain[ampName] = amp.getGain()
                self.noise[ampName] = amp.getReadNoise()
                self.meanXcorrs[ampName] = []
                self.ampKernels[ampName] = []
                self.valid[ampName] = []
        elif self.level == 'DETECTOR':
            if detectorId is None:
                for det in camera:
                    detName = det.getName()
                    self.detKernels[detName] = []
            else:
                self.detKernels[self._detectorName] = []

        return self

    def getLengths(self):
        """Return the set of lengths needed for reshaping components.

        Returns
        -------
        kernelLength : `int`
            Product of the elements of self.shape.
        smallLength : `int`
            Size of an untiled covariance.
        nObs : `int`
            Number of observation pairs used in the kernel.
        """
        kernelLength = self.shape[0] * self.shape[1]
        smallLength = int((self.shape[0] - 1)*(self.shape[1] - 1)/4)
        if self.level == 'AMP':
            nObservations = set([len(self.rawMeans[amp]) for amp in self.rawMeans])
            if len(nObservations) != 1:
                raise RuntimeError("Inconsistent number of observations found.")
            nObs = nObservations.pop()
        else:
            nObs = 0

        return (kernelLength, smallLength, nObs)

    @classmethod
    def fromDict(cls, dictionary):
        """Construct a calibration from a dictionary of properties.

        Parameters
        ----------
        dictionary : `dict`
            Dictionary of properties.

        Returns
        -------
        calib : `lsst.ip.isr.BrighterFatterKernel`
            Constructed calibration.

        Raises
        ------
        RuntimeError
            Raised if the supplied dictionary is for a different
            calibration.
            Raised if the version of the supplied dictionary is 1.0.
        """
        calib = cls()

        if calib._OBSTYPE != (found := dictionary['metadata']['OBSTYPE']):
            raise RuntimeError(f"Incorrect brighter-fatter kernel supplied.  Expected {calib._OBSTYPE}, "
                               f"found {found}")
        calib.setMetadata(dictionary['metadata'])
        calib.calibInfoFromDict(dictionary)

        calib.level = dictionary['metadata'].get('LEVEL', 'AMP')
        calib.shape = (dictionary['metadata'].get('KERNEL_DX', 0),
                       dictionary['metadata'].get('KERNEL_DY', 0))

        calibVersion = dictionary['metadata']['bfk_VERSION']
        if calibVersion == 1.0:
            calib.log.info("Old Version of brighter-fatter kernel found. Current version: "
                           f"{calib._VERSION}. The new attribute 'expIdMask' will be "
                           "populated with 'True' values, and the new attributes 'rawMeans' "
                           "and 'rawVariances' will be populated with the masked 'means' "
                           "and 'variances' values."
                           )
            # use 'means', because 'expIdMask' does not exist.
            calib.expIdMask = {amp: np.repeat(True, len(dictionary['means'][amp])) for amp in
                               dictionary['means']}
            calib.rawMeans = {amp: np.array(dictionary['means'][amp]) for amp in dictionary['means']}
            calib.rawVariances = {amp: np.array(dictionary['variances'][amp]) for amp in
                                  dictionary['variances']}
        elif calibVersion == 1.1:
            calib.expIdMask = {amp: np.array(dictionary['expIdMask'][amp]) for amp in dictionary['expIdMask']}
            calib.rawMeans = {amp: np.array(dictionary['rawMeans'][amp]) for amp in dictionary['rawMeans']}
            calib.rawVariances = {amp: np.array(dictionary['rawVariances'][amp]) for amp in
                                  dictionary['rawVariances']}
        else:
            raise RuntimeError(f"Unknown version for brighter-fatter kernel: {calibVersion}")

        # Lengths for reshape:
        _, smallLength, nObs = calib.getLengths()
        smallShapeSide = int(np.sqrt(smallLength))

        calib.rawXcorrs = {amp: np.array(dictionary['rawXcorrs'][amp]).reshape((nObs,
                                                                                smallShapeSide,
                                                                                smallShapeSide))
                           for amp in dictionary['rawXcorrs']}

        calib.gain = dictionary['gain']
        calib.noise = dictionary['noise']

        calib.meanXcorrs = {amp: np.array(dictionary['meanXcorrs'][amp]).reshape(calib.shape)
                            for amp in dictionary['rawXcorrs']}
        calib.ampKernels = {amp: np.array(dictionary['ampKernels'][amp]).reshape(calib.shape)
                            for amp in dictionary['ampKernels']}
        calib.valid = {amp: bool(value) for amp, value in dictionary['valid'].items()}
        calib.badAmps = [amp for amp, valid in dictionary['valid'].items() if valid is False]

        calib.detKernels = {det: np.array(dictionary['detKernels'][det]).reshape(calib.shape)
                            for det in dictionary['detKernels']}

        calib.updateMetadata()
        return calib

    def toDict(self):
        """Return a dictionary containing the calibration properties.

        The dictionary should be able to be round-tripped through
        `fromDict`.

        Returns
        -------
        dictionary : `dict`
            Dictionary of properties.
        """
        self.updateMetadata()

        outDict = {}
        metadata = self.getMetadata()
        outDict['metadata'] = metadata

        # Lengths for ravel:
        kernelLength, smallLength, nObs = self.getLengths()

        outDict['expIdMask'] = {amp: np.array(self.expIdMask[amp]).tolist() for amp in self.expIdMask}
        outDict['rawMeans'] = {amp: np.array(self.rawMeans[amp]).tolist() for amp in self.rawMeans}
        outDict['rawVariances'] = {amp: np.array(self.rawVariances[amp]).tolist() for amp in
                                   self.rawVariances}

        for amp in self.rawXcorrs.keys():
            # Check to see if we need to repack the data.
            correlationShape = np.array(self.rawXcorrs[amp]).shape
            if nObs != correlationShape[0]:
                if correlationShape[0] == np.sum(self.expIdMask[amp]):
                    # Repack data.
                    self.repackCorrelations(amp, correlationShape)
                else:
                    raise ValueError("Could not coerce rawXcorrs into appropriate shape "
                                     "(have %d correlations, but expect to see %d.",
                                     correlationShape[0], np.sum(self.expIdMask[amp]))

        outDict['rawXcorrs'] = {amp: np.array(self.rawXcorrs[amp]).reshape(nObs*smallLength).tolist()
                                for amp in self.rawXcorrs}
        outDict['badAmps'] = self.badAmps
        outDict['gain'] = self.gain
        outDict['noise'] = self.noise

        outDict['meanXcorrs'] = {amp: self.meanXcorrs[amp].reshape(kernelLength).tolist()
                                 for amp in self.meanXcorrs}
        outDict['ampKernels'] = {amp: self.ampKernels[amp].reshape(kernelLength).tolist()
                                 for amp in self.ampKernels}
        outDict['valid'] = self.valid

        outDict['detKernels'] = {det: self.detKernels[det].reshape(kernelLength).tolist()
                                 for det in self.detKernels}
        return outDict

    @classmethod
    def fromTable(cls, tableList):
        """Construct calibration from a list of tables.

        This method uses the `fromDict` method to create the
        calibration, after constructing an appropriate dictionary from
        the input tables.

        Parameters
        ----------
        tableList : `list` [`astropy.table.Table`]
            List of tables to use to construct the brighter-fatter
            calibration.

        Returns
        -------
        calib : `lsst.ip.isr.BrighterFatterKernel`
            The calibration defined in the tables.
        """
        ampTable = tableList[0]

        metadata = ampTable.meta
        inDict = dict()
        inDict['metadata'] = metadata

        amps = ampTable['AMPLIFIER']

        # Determine version for expected values.  The ``fromDict``
        # method can unpack either, but the appropriate fields need to
        # be supplied.
        calibVersion = metadata['bfk_VERSION']

        if calibVersion == 1.0:
            # We expect to find ``means`` and ``variances`` for this
            # case, and will construct an ``expIdMask`` from these
            # parameters in the ``fromDict`` method.
            rawMeanList = ampTable['MEANS']
            rawVarianceList = ampTable['VARIANCES']

            inDict['means'] = {amp: mean for amp, mean in zip(amps, rawMeanList)}
            inDict['variances'] = {amp: var for amp, var in zip(amps, rawVarianceList)}
        elif calibVersion == 1.1:
            # This will have ``rawMeans`` and ``rawVariances``, which
            # are filtered via the ``expIdMask`` fields.
            expIdMaskList = ampTable['EXP_ID_MASK']
            rawMeanList = ampTable['RAW_MEANS']
            rawVarianceList = ampTable['RAW_VARIANCES']

            inDict['expIdMask'] = {amp: mask for amp, mask in zip(amps, expIdMaskList)}
            inDict['rawMeans'] = {amp: mean for amp, mean in zip(amps, rawMeanList)}
            inDict['rawVariances'] = {amp: var for amp, var in zip(amps, rawVarianceList)}
        else:
            raise RuntimeError(f"Unknown version for brighter-fatter kernel: {calibVersion}")

        rawXcorrs = ampTable['RAW_XCORRS']
        gainList = ampTable['GAIN']
        noiseList = ampTable['NOISE']

        meanXcorrs = ampTable['MEAN_XCORRS']
        ampKernels = ampTable['KERNEL']
        validList = ampTable['VALID']

        inDict['rawXcorrs'] = {amp: kernel for amp, kernel in zip(amps, rawXcorrs)}
        inDict['gain'] = {amp: gain for amp, gain in zip(amps, gainList)}
        inDict['noise'] = {amp: noise for amp, noise in zip(amps, noiseList)}
        inDict['meanXcorrs'] = {amp: kernel for amp, kernel in zip(amps, meanXcorrs)}
        inDict['ampKernels'] = {amp: kernel for amp, kernel in zip(amps, ampKernels)}
        inDict['valid'] = {amp: bool(valid) for amp, valid in zip(amps, validList)}

        inDict['badAmps'] = [amp for amp, valid in inDict['valid'].items() if valid is False]

        if len(tableList) > 1:
            detTable = tableList[1]
            inDict['detKernels'] = {det: kernel for det, kernel
                                    in zip(detTable['DETECTOR'], detTable['KERNEL'])}
        else:
            inDict['detKernels'] = {}

        return cls.fromDict(inDict)

    def toTable(self):
        """Construct a list of tables containing the information in this
        calibration.

        The list of tables should create an identical calibration
        after being passed to this class's fromTable method.

        Returns
        -------
        tableList : `list` [`lsst.afw.table.Table`]
            List of tables containing the crosstalk calibration
            information.

        """
        tableList = []
        self.updateMetadata()

        # Lengths
        kernelLength, smallLength, nObs = self.getLengths()

        ampList = []
        expIdMaskList = []
        rawMeanList = []
        rawVarianceList = []
        rawXcorrs = []
        gainList = []
        noiseList = []

        meanXcorrsList = []
        kernelList = []
        validList = []

        if self.level == 'AMP':
            for amp in self.rawMeans.keys():
                ampList.append(amp)
                expIdMaskList.append(self.expIdMask[amp])
                rawMeanList.append(self.rawMeans[amp])
                rawVarianceList.append(self.rawVariances[amp])

                correlationShape = np.array(self.rawXcorrs[amp]).shape
                if nObs != correlationShape[0]:
                    if correlationShape[0] == np.sum(self.expIdMask[amp]):
                        # Repack data.
                        self.repackCorrelations(amp, correlationShape)
                    else:
                        raise ValueError("Could not coerce rawXcorrs into appropriate shape "
                                         "(have %d correlations, but expect to see %d.",
                                         correlationShape[0], np.sum(self.expIdMask[amp]))

                rawXcorrs.append(np.array(self.rawXcorrs[amp]).reshape(nObs*smallLength).tolist())
                gainList.append(self.gain[amp])
                noiseList.append(self.noise[amp])

                meanXcorrsList.append(self.meanXcorrs[amp].reshape(kernelLength).tolist())
                kernelList.append(self.ampKernels[amp].reshape(kernelLength).tolist())
                validList.append(int(self.valid[amp] and not (amp in self.badAmps)))

        ampTable = Table({'AMPLIFIER': ampList,
                          'EXP_ID_MASK': expIdMaskList,
                          'RAW_MEANS': rawMeanList,
                          'RAW_VARIANCES': rawVarianceList,
                          'RAW_XCORRS': rawXcorrs,
                          'GAIN': gainList,
                          'NOISE': noiseList,
                          'MEAN_XCORRS': meanXcorrsList,
                          'KERNEL': kernelList,
                          'VALID': validList,
                          })

        ampTable.meta = self.getMetadata().toDict()
        tableList.append(ampTable)

        if len(self.detKernels):
            detList = []
            kernelList = []
            for det in self.detKernels.keys():
                detList.append(det)
                kernelList.append(self.detKernels[det].reshape(kernelLength).tolist())

            detTable = Table({'DETECTOR': detList,
                              'KERNEL': kernelList})
            detTable.meta = self.getMetadata().toDict()
            tableList.append(detTable)

        return tableList

    def repackCorrelations(self, amp, correlationShape):
        """If the correlations were masked, they need to be repacked into the
        correct shape.

        Parameters
        ----------
        amp : `str`
            Amplifier needing repacked.
        correlationShape : `tuple` [`int`], (3, )
            Shape the correlations are expected to take.
        """
        repackedCorrelations = []
        idx = 0
        for maskValue in self.expIdMask[amp]:
            if maskValue:
                repackedCorrelations.append(self.rawXcorrs[amp][idx])
                idx += 1
            else:
                repackedCorrelations.append(np.full((correlationShape[1], correlationShape[2]), np.nan))
        self.rawXcorrs[amp] = repackedCorrelations

    # Implementation methods
    def makeDetectorKernelFromAmpwiseKernels(self, detectorName, ampsToExclude=[]):
        """Average the amplifier level kernels to create a detector level
        kernel.
        """
        inKernels = np.array([self.ampKernels[amp] for amp in
                              self.ampKernels if amp not in ampsToExclude])
        averagingList = np.transpose(inKernels)
        avgKernel = np.zeros_like(inKernels[0])
        sctrl = afwMath.StatisticsControl()
        sctrl.setNumSigmaClip(5.0)
        for i in range(np.shape(avgKernel)[0]):
            for j in range(np.shape(avgKernel)[1]):
                avgKernel[i, j] = afwMath.makeStatistics(averagingList[i, j],
                                                         afwMath.MEANCLIP, sctrl).getValue()

        self.detKernels[detectorName] = avgKernel

    def replaceDetectorKernelWithAmpKernel(self, ampName, detectorName):
        self.detKernel[detectorName] = self.ampKernel[ampName]
