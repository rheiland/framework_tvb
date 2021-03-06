# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and 
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2013, Baycrest Centre for Geriatric Care ("Baycrest")
#
# This program is free software; you can redistribute it and/or modify it under 
# the terms of the GNU General Public License version 2 as published by the Free
# Software Foundation. This program is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
# License for more details. You should have received a copy of the GNU General 
# Public License along with this program; if not, you can download it here
# http://www.gnu.org/licenses/old-licenses/gpl-2.0
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#
"""
.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Ionel Ortelecan <ionel.ortelecan@codemart.ro>
"""

from tvb.core.entities.storage import dao
from tvb.core.adapters.abcremover import ABCRemover
from tvb.datatypes.time_series import TimeSeriesSurface
from tvb.datatypes.surfaces import LocalConnectivity, RegionMapping
from tvb.datatypes.patterns_data import StimuliSurfaceData
from tvb.core.services.exceptions import RemoveDataTypeException


class SurfaceRemover(ABCRemover):
    """
    Surface specific validations at remove time.
    """

    def __init__(self, handled_datatype):
        ABCRemover.__init__(self, handled_datatype)


    def remove_datatype(self, skip_validation=False):
        """
        Called when a Surface is to be removed.
        """
        if not skip_validation:
            associated_ts = dao.get_generic_entity(TimeSeriesSurface, self.handled_datatype.gid, '_surface')
            associated_rm = dao.get_generic_entity(RegionMapping, self.handled_datatype.gid, '_surface')
            associated_lc = dao.get_generic_entity(LocalConnectivity, self.handled_datatype.gid, '_surface')
            associated_stim = dao.get_generic_entity(StimuliSurfaceData, self.handled_datatype.gid, '_surface')
            error_msg = "Surface cannot be removed because is still used by a "
            if len(associated_ts) > 0:
                raise RemoveDataTypeException(error_msg + " TimeSeriesSurface.")
            if len(associated_rm) > 0:
                raise RemoveDataTypeException(error_msg + " RegionMapping.")
            if len(associated_lc) > 0:
                raise RemoveDataTypeException(error_msg + " LocalConnectivity.")
            if len(associated_stim) > 0:
                raise RemoveDataTypeException(error_msg + " StimuliSurfaceData.")
            
        ABCRemover.remove_datatype(self, skip_validation)
        
    
        
        
