# -*- coding: utf-8 -*-
#
# Copyright © 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the License
# (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied, including the
# implied warranties of MERCHANTABILITY, NON-INFRINGEMENT, or FITNESS FOR A
# PARTICULAR PURPOSE.
# You should have received a copy of GPLv2 along with this software; if not,
# see http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt

import os
import unittest
import mock
from nectar.config import DownloaderConfig
from nectar.report import DownloadReport
from nectar.request import DownloadRequest

from pulp_rpm.common import models, constants
from pulp_rpm.plugins.importers.yum.listener import DistroFileListener
from pulp_rpm.plugins.importers.yum.parse import treeinfo
from pulp_rpm.plugins.importers.yum.report import DistributionReport
import model_factory


class TestSync(unittest.TestCase):
    def setUp(self):
        self.conduit = mock.MagicMock()
        self.feed = 'http://www.pulpproject.org/'
        self.config = DownloaderConfig()
        self.report = DistributionReport()
        self.progress_callback = mock.MagicMock()

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True, return_value='/usr')
    @mock.patch.object(treeinfo, 'get_treefile', return_value=None, autospec=True)
    def test_treefile_not_found(self, mock_get_treefile, mock_mkdtemp, mock_rmtree):
        treeinfo.sync(self.conduit, self.feed, '/root', self.config, self.report, self.progress_callback)

        self.assertEqual(self.report['state'], constants.STATE_COMPLETE)
        mock_mkdtemp.assert_called_once_with(dir='/root')
        mock_rmtree.assert_called_once_with('/usr', ignore_errors=True)

    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True, return_value='/usr')
    @mock.patch.object(treeinfo, 'get_treefile', return_value=__file__, autospec=True)
    def test_treefile_not_parsable(self, mock_get_treefile, mock_mkdtemp, mock_rmtree):
        treeinfo.sync(self.conduit, self.feed, '/root', self.config, self.report, self.progress_callback)

        self.assertEqual(self.report['state'], constants.STATE_FAILED)
        mock_mkdtemp.assert_called_once_with(dir='/root')
        mock_rmtree.assert_called_once_with('/usr', ignore_errors=True)

    # sorry about all of these mocks
    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader', autospec=True)
    @mock.patch.object(treeinfo, 'DistroFileListener', autospec=True)
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True, return_value='/usr')
    @mock.patch.object(treeinfo, 'get_treefile',
                       return_value=os.path.join(os.path.dirname(__file__), '../data/treeinfo-rhel5'),
                       autospec=True)
    def test_some_files_failed(self, mock_get_treefile, mock_mkdtemp, mock_rmtree,
                               mock_listener, mock_create_downloader, mock_makedirs):
        mock_listener.return_value = DistroFileListener(self.report, self.progress_callback)
        report = DownloadReport('http://www.pulpproject.org', '/usr/foo')
        mock_listener.return_value.download_failed(report)

        treeinfo.sync(self.conduit, self.feed, '/root', self.config, self.report, self.progress_callback)

        self.assertEqual(self.report['state'], constants.STATE_FAILED)
        mock_rmtree.assert_called_once_with('/usr', ignore_errors=True)
        self.assertEqual(self.report['error_details'][0][0], report.url)

    # sorry about all of these mocks
    @mock.patch('os.chmod', autospec=True)
    @mock.patch('os.makedirs', autospec=True)
    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader', autospec=True)
    @mock.patch('shutil.rmtree', autospec=True)
    @mock.patch('shutil.move', autospec=True)
    @mock.patch('tempfile.mkdtemp', autospec=True, return_value='/usr')
    @mock.patch.object(treeinfo, 'get_treefile',
                       return_value=os.path.join(os.path.dirname(__file__), '../data/treeinfo-rhel5'),
                       autospec=True)
    def test_success(self, mock_get_treefile, mock_mkdtemp, mock_move, mock_rmtree,
                               mock_create_downloader, mock_makedirs, mock_chmod):
        new_unit = model_factory.distribution_units(1)[0]
        new_unit.storage_path = '/root/a/b/c'
        self.conduit.init_unit.return_value = new_unit

        treeinfo.sync(self.conduit, self.feed, '/root', self.config, self.report, self.progress_callback)

        self.assertEqual(self.report['state'], constants.STATE_COMPLETE)
        self.assertEqual(mock_rmtree.call_count, 2)
        mock_rmtree.assert_any_call('/usr', ignore_errors=True)
        mock_rmtree.assert_any_call(self.conduit.init_unit.return_value.storage_path, ignore_errors=True)
        self.conduit.save_unit.assert_called_once_with(self.conduit.init_unit.return_value)
        mock_move.assert_called_once_with('/usr', self.conduit.init_unit.return_value.storage_path)


class TestGetTreefile(unittest.TestCase):
    def setUp(self):
        self.feed = 'http://www.pulpproject.org/'
        self.tmp_dir = '/root' # ensures we don't actually write anything
        self.config = DownloaderConfig()
        self.fake_success_count = 0

    def fake_success(self, feed, nectar_config, listener):
        if self.fake_success_count == 1:
            listener.succeeded_reports.append(mock.MagicMock())
        self.fake_success_count += 1
        return mock.DEFAULT

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader',
                autospec=True)
    def test_first_filename_found(self, mock_create_downloader):
        self.fake_success_count = 1
        mock_create_downloader.side_effect = self.fake_success

        ret = treeinfo.get_treefile(self.feed, self.tmp_dir, self.config)

        self.assertEqual(ret, os.path.join(self.tmp_dir, constants.TREE_INFO_LIST[0]))

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader',
                autospec=True)
    def test_second_filename_found(self, mock_create_downloader):
        mock_create_downloader.side_effect = self.fake_success

        ret = treeinfo.get_treefile(self.feed, self.tmp_dir, self.config)

        self.assertEqual(ret, os.path.join(self.tmp_dir, constants.TREE_INFO_LIST[1]))

    @mock.patch('pulp_rpm.plugins.importers.yum.repomd.nectar_factory.create_downloader',
                autospec=True)
    def test_not_found(self, mock_create_downloader):
        ret = treeinfo.get_treefile(self.feed, self.tmp_dir, self.config)

        self.assertTrue(ret is None)


class TestFileToDownloadRequest(unittest.TestCase):
    def setUp(self):
        self.file_dict = {
            'relativepath': 'a/b/myfile',
            'checksum': 'abc123',
            'checksumtype': 'sha256',
        }
        self.feed = 'http://www.pulpproject.org/'

    @mock.patch('os.path.exists', autospec=True, return_value=True)
    def test_path_exists(self, mock_exists):
        ret = treeinfo.file_to_download_request(self.file_dict, self.feed, '/root')

        self.assertTrue(isinstance(ret, DownloadRequest))
        self.assertEqual(ret.destination, '/root/a/b/myfile')
        self.assertEqual(ret.url, 'http://www.pulpproject.org/a/b/myfile')
        mock_exists.assert_called_once_with('/root/a/b')

    @mock.patch('os.makedirs', autospec=True)
    def test_path_does_not_exist(self, mock_makedirs):
        ret = treeinfo.file_to_download_request(self.file_dict, self.feed, '/root')

        self.assertTrue(isinstance(ret, DownloadRequest))
        self.assertEqual(ret.destination, '/root/a/b/myfile')
        self.assertEqual(ret.url, 'http://www.pulpproject.org/a/b/myfile')
        mock_makedirs.assert_called_once_with('/root/a/b')


class TestRealData(unittest.TestCase):
    def test_rhel5(self):
        path = os.path.join(os.path.dirname(__file__), '../data/treeinfo-rhel5')

        model, files = treeinfo.parse_treefile(path)

        self.assertTrue(isinstance(model, models.Distribution))
        self.assertEqual(model.id, 'ks-Red Hat Enterprise Linux Server-5.9-x86_64')

        self.assertEqual(len(files), 19)
        for item in files:
            self.assertTrue(item['relativepath'])

    def test_rhel6(self):
        path = os.path.join(os.path.dirname(__file__), '../data/treeinfo-rhel6')

        model, files = treeinfo.parse_treefile(path)

        self.assertTrue(isinstance(model, models.Distribution))
        self.assertEqual(model.id, 'ks-Red Hat Enterprise Linux-Server-6.4-x86_64')

        self.assertEqual(len(files), 7)
        for item in files:
            self.assertTrue(item['relativepath'])
            self.assertTrue(item['checksum'])
            self.assertEqual(item['checksumtype'], 'sha256')

    def test_unparsable(self):
        # make it try to read this python file as a config file
        self.assertRaises(ValueError, treeinfo.parse_treefile, __file__)