# Copyright 2011, Vinothan N. Manoharan, Thomas G. Dimiduk, Rebecca
# W. Perry, Jerome Fung, and Ryan McGorty
#
# This file is part of Holopy.
#
# Holopy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Holopy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Holopy.  If not, see <http://www.gnu.org/licenses/>.
'''
Tests adda based DDA calculations

.. moduleauthor:: Thomas G. Dimiduk <tdimiduk@physics.harvard.edu>
'''
from __future__ import division


import holopy as hp
import numpy as np
from nose.tools import assert_raises
from numpy.testing import assert_, assert_almost_equal, dec
from nose.tools import with_setup
from nose.plugins.attrib import attr

from scatterpy.scatterer import Sphere, CoatedSphere
from scatterpy.scatterer import Composite, SphereCluster

from scatterpy.theory import Mie, DDA
from scatterpy.theory.dda import DependencyMissing
import scatterpy
from scatterpy.errors import TheoryNotCompatibleError
from holopy.optics import (WavelengthNotSpecified, PixelScaleNotSpecified,
                           MediumIndexNotSpecified)
from scatterpy.scatterer.voxelated import ScattererByFunction
from common import assert_allclose
import common

import os.path

def missing_dependencies():
    try:
        DDA(None)
    except DependencyMissing:
        return True
    return False
    

# nose setup/teardown methods
def setup_optics():
    # set up optics class for use in several test functions
    global optics
    wavelen = 658e-3
    polarization = [0., 1.0]
    divergence = 0
    pixel_scale = [.1151, .1151]
    index = 1.33
    
    optics = hp.optics.Optics(wavelen=wavelen, index=index,
                                  pixel_scale=pixel_scale,
                                  polarization=polarization,
                                  divergence=divergence)
    
def teardown_optics():
    global optics
    del optics


@dec.skipif(missing_dependencies(), "a-dda not installed")
@attr('fast')
@with_setup(setup=setup_optics, teardown=teardown_optics)
def test_DDA_construction():
    theory = DDA(optics)
    assert_((theory.imshape == (256,256)).all())
    theory = DDA(optics, imshape=(100,100))
    assert_((theory.imshape == (100,100)).all())

    # test with single value instead of tuple
    theory = DDA(optics, imshape=128)
    assert_((theory.imshape == (128,128)).all())

    # construct with optics
    theory = DDA(imshape=256, optics=optics)
    assert_(theory.optics.index == 1.33)

@dec.skipif(missing_dependencies(), "a-dda not installed")
@attr('medium')
@with_setup(setup=setup_optics, teardown=teardown_optics)
def test_DDA_sphere():
    sc = Sphere(n=1.59, r=3e-1, center=(1, -1, 30))
    dda = DDA(imshape=128, optics=optics)
    mie = Mie(imshape=128, optics=optics)

    mie_holo = mie.calc_holo(sc)
    dda_holo = dda.calc_holo(sc)
    assert_allclose(mie_holo, dda_holo, rtol=.0015)

@dec.skipif(missing_dependencies(), "a-dda not installed")
@attr('slow')
@with_setup(setup=setup_optics, teardown=teardown_optics)
def test_DDA_voxelated():
    # test that DDA voxelated gets the same results as DDA sphere as a basic
    # sanity check of dda

    n = 1.59
    center = (1, 1, 30)
    r = .3
    
    sc = Sphere(n=n, r=r, center = center)
    dda = DDA(imshape=128, optics=optics)

    sphere_holo = dda.calc_holo(sc)

    geom = np.loadtxt(os.path.join(dda._last_result_dir, 'sphere.geom'),
                      skiprows=3)

    # hardcode size for now.  This is available in the log of the adda output,
    # so we could get it with a parser, but this works for now, not that it
    # could change if we change the size of the scatterer (and thus lead to a
    # fail)
    # FAIL HINT: grid size hardcoded, check that it is what dda sphere outputs
    dpl_dia = 16
    
    sphere = np.zeros((dpl_dia,dpl_dia,dpl_dia))

    for point in geom:
        x, y, z = point
        sphere[x, y, z] = 1

    sphere = sphere.astype('float') * n
    
    dpl = 13.2569

    # this would nominally be the correct way to determine dpl, but because of
    #volume correction within adda, this is not as accurate (only 
    #dpl = dpl_dia * optics.med_wavelen / (r*2)
    
    s = scatterpy.scatterer.voxelated.VoxelatedScatterer(sphere, center, dpl)

    gen_holo = dda.calc_holo(s)

    assert_allclose(sphere_holo, gen_holo, rtol=1e-3)

@dec.skipif(missing_dependencies(), "a-dda not installed")
@with_setup(setup=setup_optics, teardown=teardown_optics)
def test_voxelated_complex():
    o = hp.Optics(wavelen=.66, index=1.33, pixel_scale=.1)
    s = scatterpy.scatterer.Sphere(n = 1.2+2j, r = .2, center = (5,5,5))

    def sphere(r):
        rsq = r**2
        def test(point):
            return (point**2).sum() < rsq
        return test

    sv = ScattererByFunction(sphere(s.r), s.n, [[-s.r, s.r], [-s.r, s.r], [-s.r,
    s.r]], center = s.center)

    dda = DDA(o, 50)
    holo_dda = dda.calc_holo(sv)
    common.verify(holo_dda, 'dda_voxelated_complex', rtol=1e-5)

    
@attr('medium')
@dec.skipif(missing_dependencies(), "a-dda not installed")
@with_setup(setup=setup_optics, teardown=teardown_optics)
def test_DDA_coated():
    cs = scatterpy.scatterer.CoatedSphere(
        center=[7.141442573813124, 7.160766866147957, 11.095409800342143],
        n=[(1.27121212428+0j), (1.49+0j)], r=[.1-0.0055, 0.1])

    dda = DDA(imshape=128, optics=optics)
    lmie = scatterpy.theory.Mie(imshape=128, optics=optics)

    lmie_holo = lmie.calc_holo(cs)
    dda_holo = dda.calc_holo(cs)

    assert_allclose(lmie_holo, dda_holo, rtol = 5e-5)

@dec.skipif(missing_dependencies(), "a-dda not installed")
@with_setup(setup=setup_optics, teardown=teardown_optics)
def test_Ellipsoid_dda():
    e = scatterpy.scatterer.Ellipsoid(1.5, r = (.5, .1, .1), center = (1, -1, 10))
    dda = scatterpy.theory.DDA(hp.Optics(wavelen=.66, pixel_scale=.1, index=1.33), 100)
    h = dda.calc_holo(e)

    assert_almost_equal(h.max(), 1.3152766077267062)
    assert_almost_equal(h.mean(), 0.99876620628942114)
    assert_almost_equal(h.std(), 0.06453155384119547)

    