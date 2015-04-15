import os
from xml.etree import ElementTree

from pulp.plugins.util.metadata_writer import XmlFileContext

from pulp_rpm.plugins.distributors.yum.metadata.metadata import REPO_DATA_DIR_NAME
from pulp_rpm.yum_plugin import util


_LOG = util.getLogger(__name__)

PRESTO_DELTA_FILE_NAME = 'prestodelta.xml.gz'


class PrestodeltaXMLFileContext(XmlFileContext):

    def __init__(self, working_dir, checksum_type=None):

        metadata_file_path = os.path.join(working_dir, REPO_DATA_DIR_NAME, PRESTO_DELTA_FILE_NAME)
        super(PrestodeltaXMLFileContext, self).__init__(metadata_file_path,
                                                        root_tag='prestodelta',
                                                        checksum_type=checksum_type)

    def add_unit_metadata(self, delta_unit):

        new_package_attributes = {'name': delta_unit.metadata['new_package'],
                                  'epoch': delta_unit.unit_key['epoch'],
                                  'version': delta_unit.unit_key['version'],
                                  'release': delta_unit.unit_key['release'],
                                  'arch': delta_unit.metadata['arch']}

        new_package_element = ElementTree.Element('newpackage', new_package_attributes)

        delta_attributes = {'oldepoch': delta_unit.metadata['oldepoch'],
                            'oldversion': delta_unit.metadata['oldversion'],
                            'oldrelease': delta_unit.metadata['oldrelease']}

        delta_element = ElementTree.SubElement(new_package_element, 'delta', delta_attributes)

        file_name_element = ElementTree.SubElement(delta_element, 'filename')
        unit_filename = os.path.basename(delta_unit.unit_key['filename'])
        file_name_element.text = os.path.join('drpms', unit_filename)

        sequence_element = ElementTree.SubElement(delta_element, 'sequence')
        sequence_element.text = delta_unit.metadata['sequence']

        size_element = ElementTree.SubElement(delta_element, 'size')
        size_element.text = str(delta_unit.metadata['size'])

        checksum_attributes = {'type': delta_unit.unit_key['checksumtype']}

        checksum_element = ElementTree.SubElement(delta_element, 'checksum', checksum_attributes)
        checksum_element.text = delta_unit.unit_key['checksum']

        new_package_element_string = ElementTree.tostring(new_package_element, 'utf-8')

        _LOG.debug('Writing prestodelta unit metadata:\n' + new_package_element_string)

        self.metadata_file_handle.write(new_package_element_string + '\n')
