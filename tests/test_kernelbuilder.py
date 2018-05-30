# Copyright (c) 2018 Red Hat, Inc. All rights reserved. This copyrighted
# material is made available to anyone wishing to use, modify, copy, or
# redistribute it subject to the terms and conditions of the GNU General Public
# License v.2 or later.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
"""Test cases for KernelBuilder class."""

from __future__ import division
import unittest
import tempfile
import shutil
import os
import subprocess
import mock
from mock import Mock

import skt.kernelbuilder as kernelbuilder


class KBuilderTest(unittest.TestCase):
    # (Too many instance attributes) pylint: disable=R0902
    """Test cases for KernelBuilder class."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmpconfig = tempfile.NamedTemporaryFile()
        self.kbuilder = kernelbuilder.KernelBuilder(
            self.tmpdir,
            self.tmpconfig.name
        )
        self.m_popen = Mock()
        self.m_popen.returncode = 0
        self.ctx_popen = mock.patch('subprocess.Popen',
                                    Mock(return_value=self.m_popen))
        self.ctx_check_call = mock.patch('subprocess.check_call', Mock())
        self.m_io_open = Mock()
        self.m_io_open.__enter__ = lambda *args: self.m_io_open
        self.m_io_open.__exit__ = lambda *args: None
        self.ctx_io_open = mock.patch('io.open',
                                      Mock(return_value=self.m_io_open))
        self.kernel_tarball = 'linux-4.16.0.tar.gz'
        self.success_str = 'Tarball successfully created in ./{}\n'
        self.success_str = self.success_str.format(self.kernel_tarball)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_mktgz_clean(self):
        """
        Check if `mrproper` target is called when `clean` is True and not
        called when `clean` is False.
        """
        with self.ctx_popen, self.ctx_check_call as m_check_call:
            self.assertRaises(Exception, self.kbuilder_mktgz_silent,
                              clean=True)
            self.assertEqual(
                m_check_call.mock_calls[0],
                mock.call(['make', '-C', self.tmpdir, 'mrproper'])
            )
            m_check_call.reset_mock()
            self.assertRaises(Exception, self.kbuilder_mktgz_silent,
                              clean=False)
            self.assertNotEqual(
                m_check_call.mock_calls[0],
                mock.call(['make', '-C', self.tmpdir, 'mrproper']),
            )

    def test_mktgz_parsing_error(self):
        """Check if ParsingError is raised when no kernel is found in stdout"""
        self.m_io_open.readlines = Mock(return_value=['foo\n', 'bar\n'])
        with self.ctx_popen, self.ctx_check_call, self.ctx_io_open:
            self.assertRaises(
                kernelbuilder.ParsingError,
                self.kbuilder_mktgz_silent
            )

    def test_mktgz_ioerror(self):
        """Check if IOError is raised when tarball path does not exist"""
        self.m_io_open.readlines = Mock(
            return_value=['foo\n', self.success_str]
        )
        with self.ctx_io_open, self.ctx_popen, self.ctx_check_call:
            self.assertRaises(IOError, self.kbuilder_mktgz_silent)

    def test_mktgz_make_fail(self):
        """
        Check if subprocess.CalledProcessError is raised when make command
        fails to spawn.
        """
        self.m_popen.returncode = 1
        with self.ctx_popen:
            self.assertRaises(subprocess.CalledProcessError,
                              self.kbuilder_mktgz_silent)

    def test_mktgz_success(self):
        """Check if mktgz can finish successfully"""
        self.m_io_open.readlines = Mock(
            return_value=['foo\n', self.success_str, 'bar']
        )
        self.m_popen.returncode = 0
        with self.ctx_io_open, self.ctx_popen, self.ctx_check_call:
            with open(os.path.join(self.tmpdir, self.kernel_tarball), 'w'):
                pass
            full_path = self.kbuilder_mktgz_silent()
            self.assertEqual(os.path.join(self.tmpdir, self.kernel_tarball),
                             full_path)

    def kbuilder_mktgz_silent(self, *args, **kwargs):
        """Run self.kbuilder.mktgz with disabled output"""
        with mock.patch('sys.stdout'):
            return self.kbuilder.mktgz(*args, **kwargs)

    def test_extra_make_args(self):
        """Ensure KernelBuilder handles extra_make_args properly"""
        extra_make_args_example = '-j10'
        kbuilder = kernelbuilder.KernelBuilder(
            self.tmpdir,
            self.tmpconfig.name,
            extra_make_args=extra_make_args_example
        )
        self.assertEqual(kbuilder.extra_make_args, [extra_make_args_example])

    def test_getrelease(self):
        """Ensure get_release() handles a valid kernel version string"""
        mock_prepare = mock.patch("skt.kernelbuilder.KernelBuilder.prepare")

        kernel_version = '4.17.0-rc6+\n'
        mock_popen = self.ctx_popen
        self.m_popen.communicate = Mock(return_value=(kernel_version, None))

        with mock_popen, mock_prepare:
            result = self.kbuilder.getrelease()
            self.assertEqual(kernel_version.strip(), result)

    def test_getrelease_regex_fail(self):
        """Ensure get_release() fails if the regex doesn't match"""
        mock_prepare = mock.patch("skt.kernelbuilder.KernelBuilder.prepare")

        mock_popen = self.ctx_popen
        self.m_popen.communicate = Mock(return_value=('this_is_silly', None))

        with mock_popen, mock_prepare:
            with self.assertRaises(Exception):
                self.kbuilder.getrelease()
