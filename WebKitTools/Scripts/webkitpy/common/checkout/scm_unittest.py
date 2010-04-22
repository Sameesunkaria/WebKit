# Copyright (C) 2009 Google Inc. All rights reserved.
# Copyright (C) 2009 Apple Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#    * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#    * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import with_statement

import base64
import codecs
import getpass
import os
import os.path
import re
import stat
import subprocess
import tempfile
import unittest
import urllib

from datetime import date
from webkitpy.common.checkout.api import Checkout
from webkitpy.common.checkout.scm import detect_scm_system, SCM, SVN, CheckoutNeedsUpdate, commit_error_handler
from webkitpy.common.config.committers import Committer  # FIXME: This should not be needed
from webkitpy.common.net.bugzilla import Attachment # FIXME: This should not be needed
from webkitpy.common.system.executive import Executive, run_command, ScriptError

# Eventually we will want to write tests which work for both scms. (like update_webkit, changed_files, etc.)
# Perhaps through some SCMTest base-class which both SVNTest and GitTest inherit from.

# FIXME: This should be unified into one of the executive.py commands!
def run_silent(args, cwd=None):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    process.communicate() # ignore output
    exit_code = process.wait()
    if exit_code:
        raise ScriptError('Failed to run "%s"  exit_code: %d  cwd: %s' % (args, exit_code, cwd))


def write_into_file_at_path(file_path, contents, encoding="utf-8"):
    with codecs.open(file_path, "w", encoding) as file:
        file.write(contents)


def read_from_path(file_path, encoding="utf-8"):
    with codecs.open(file_path, "r", encoding) as file:
        return file.read()


# Exists to share svn repository creation code between the git and svn tests
class SVNTestRepository:
    @classmethod
    def _svn_add(cls, path):
        run_command(["svn", "add", path])

    @classmethod
    def _svn_commit(cls, message):
        run_command(["svn", "commit", "--quiet", "--message", message])

    @classmethod
    def _setup_test_commits(cls, test_object):
        # Add some test commits
        os.chdir(test_object.svn_checkout_path)

        write_into_file_at_path("test_file", "test1")
        cls._svn_add("test_file")
        cls._svn_commit("initial commit")

        write_into_file_at_path("test_file", "test1test2")
        # This used to be the last commit, but doing so broke
        # GitTest.test_apply_git_patch which use the inverse diff of the last commit.
        # svn-apply fails to remove directories in Git, see:
        # https://bugs.webkit.org/show_bug.cgi?id=34871
        os.mkdir("test_dir")
        # Slash should always be the right path separator since we use cygwin on Windows.
        test_file3_path = "test_dir/test_file3"
        write_into_file_at_path(test_file3_path, "third file")
        cls._svn_add("test_dir")
        cls._svn_commit("second commit")

        write_into_file_at_path("test_file", "test1test2test3\n")
        write_into_file_at_path("test_file2", "second file")
        cls._svn_add("test_file2")
        cls._svn_commit("third commit")

        write_into_file_at_path("test_file", "test1test2test3\ntest4\n")
        cls._svn_commit("fourth commit")

        # svn does not seem to update after commit as I would expect.
        run_command(['svn', 'update'])

    @classmethod
    def setup(cls, test_object):
        # Create an test SVN repository
        test_object.svn_repo_path = tempfile.mkdtemp(suffix="svn_test_repo")
        test_object.svn_repo_url = "file://%s" % test_object.svn_repo_path # Not sure this will work on windows
        # git svn complains if we don't pass --pre-1.5-compatible, not sure why:
        # Expected FS format '2'; found format '3' at /usr/local/libexec/git-core//git-svn line 1477
        run_command(['svnadmin', 'create', '--pre-1.5-compatible', test_object.svn_repo_path])

        # Create a test svn checkout
        test_object.svn_checkout_path = tempfile.mkdtemp(suffix="svn_test_checkout")
        run_command(['svn', 'checkout', '--quiet', test_object.svn_repo_url, test_object.svn_checkout_path])

        cls._setup_test_commits(test_object)

    @classmethod
    def tear_down(cls, test_object):
        run_command(['rm', '-rf', test_object.svn_repo_path])
        run_command(['rm', '-rf', test_object.svn_checkout_path])

        # Now that we've deleted the checkout paths, cwddir may be invalid
        # Change back to a valid directory so that later calls to os.getcwd() do not fail.
        os.chdir(detect_scm_system(os.path.dirname(__file__)).checkout_root)

# For testing the SCM baseclass directly.
class SCMClassTests(unittest.TestCase):
    def setUp(self):
        self.dev_null = open(os.devnull, "w") # Used to make our Popen calls quiet.

    def tearDown(self):
        self.dev_null.close()

    def test_run_command_with_pipe(self):
        input_process = subprocess.Popen(['echo', 'foo\nbar'], stdout=subprocess.PIPE, stderr=self.dev_null)
        self.assertEqual(run_command(['grep', 'bar'], input=input_process.stdout), "bar\n")

        # Test the non-pipe case too:
        self.assertEqual(run_command(['grep', 'bar'], input="foo\nbar"), "bar\n")

        command_returns_non_zero = ['/bin/sh', '--invalid-option']
        # Test when the input pipe process fails.
        input_process = subprocess.Popen(command_returns_non_zero, stdout=subprocess.PIPE, stderr=self.dev_null)
        self.assertTrue(input_process.poll() != 0)
        self.assertRaises(ScriptError, run_command, ['grep', 'bar'], input=input_process.stdout)

        # Test when the run_command process fails.
        input_process = subprocess.Popen(['echo', 'foo\nbar'], stdout=subprocess.PIPE, stderr=self.dev_null) # grep shows usage and calls exit(2) when called w/o arguments.
        self.assertRaises(ScriptError, run_command, command_returns_non_zero, input=input_process.stdout)

    def test_error_handlers(self):
        git_failure_message="Merge conflict during commit: Your file or directory 'WebCore/ChangeLog' is probably out-of-date: resource out of date; try updating at /usr/local/libexec/git-core//git-svn line 469"
        svn_failure_message="""svn: Commit failed (details follow):
svn: File or directory 'ChangeLog' is out of date; try updating
svn: resource out of date; try updating
"""
        command_does_not_exist = ['does_not_exist', 'invalid_option']
        self.assertRaises(OSError, run_command, command_does_not_exist)
        self.assertRaises(OSError, run_command, command_does_not_exist, error_handler=Executive.ignore_error)

        command_returns_non_zero = ['/bin/sh', '--invalid-option']
        self.assertRaises(ScriptError, run_command, command_returns_non_zero)
        # Check if returns error text:
        self.assertTrue(run_command(command_returns_non_zero, error_handler=Executive.ignore_error))

        self.assertRaises(CheckoutNeedsUpdate, commit_error_handler, ScriptError(output=git_failure_message))
        self.assertRaises(CheckoutNeedsUpdate, commit_error_handler, ScriptError(output=svn_failure_message))
        self.assertRaises(ScriptError, commit_error_handler, ScriptError(output='blah blah blah'))


# GitTest and SVNTest inherit from this so any test_ methods here will be run once for this class and then once for each subclass.
class SCMTest(unittest.TestCase):
    def _create_patch(self, patch_contents):
        patch_path = os.path.join(self.svn_checkout_path, 'patch.diff')
        write_into_file_at_path(patch_path, patch_contents)
        patch = {}
        patch['bug_id'] = '12345'
        patch['url'] = 'file://%s' % urllib.pathname2url(patch_path)

        attachment = Attachment(patch, None) # FIXME: This is a hack, scm.py shouldn't be fetching attachment data.
        joe_cool = Committer(name="Joe Cool", email_or_emails=None)
        attachment._reviewer = joe_cool

        return attachment

    def _setup_webkittools_scripts_symlink(self, local_scm):
        webkit_scm = detect_scm_system(os.path.dirname(os.path.abspath(__file__)))
        webkit_scripts_directory = webkit_scm.scripts_directory()
        local_scripts_directory = local_scm.scripts_directory()
        os.mkdir(os.path.dirname(local_scripts_directory))
        os.symlink(webkit_scripts_directory, local_scripts_directory)

    # Tests which both GitTest and SVNTest should run.
    # FIXME: There must be a simpler way to add these w/o adding a wrapper method to both subclasses
    def _shared_test_commit_with_message(self, username="dbates@webkit.org"):
        write_into_file_at_path('test_file', 'more test content')
        commit_text = self.scm.commit_with_message("another test commit", username)
        self.assertEqual(self.scm.svn_revision_from_commit_text(commit_text), '5')

        self.scm.dryrun = True
        write_into_file_at_path('test_file', 'still more test content')
        commit_text = self.scm.commit_with_message("yet another test commit", username)
        self.assertEqual(self.scm.svn_revision_from_commit_text(commit_text), '0')

    def _shared_test_changed_files(self):
        write_into_file_at_path("test_file", "changed content")
        self.assertEqual(self.scm.changed_files(), ["test_file"])
        write_into_file_at_path("test_dir/test_file3", "new stuff")
        self.assertEqual(self.scm.changed_files(), ["test_dir/test_file3", "test_file"])
        old_cwd = os.getcwd()
        os.chdir("test_dir")
        # Validate that changed_files does not change with our cwd, see bug 37015.
        self.assertEqual(self.scm.changed_files(), ["test_dir/test_file3", "test_file"])
        os.chdir(old_cwd)

    def _shared_test_added_files(self):
        write_into_file_at_path("test_file", "changed content")
        self.assertEqual(self.scm.added_files(), [])

        write_into_file_at_path("added_file", "new stuff")
        self.scm.add("added_file")

        os.mkdir("added_dir")
        write_into_file_at_path("added_dir/added_file2", "new stuff")
        self.scm.add("added_dir")

        # SVN reports directory changes, Git does not.
        added_files = self.scm.added_files()
        if "added_dir" in added_files:
            added_files.remove("added_dir")
        self.assertEqual(added_files, ["added_dir/added_file2", "added_file"])

        # Test also to make sure clean_working_directory removes added files
        self.scm.clean_working_directory()
        self.assertEqual(self.scm.added_files(), [])
        self.assertFalse(os.path.exists("added_file"))
        self.assertFalse(os.path.exists("added_dir"))

    def _shared_test_changed_files_for_revision(self):
        # SVN reports directory changes, Git does not.
        changed_files = self.scm.changed_files_for_revision(2)
        if "test_dir" in changed_files:
            changed_files.remove("test_dir")
        self.assertEqual(changed_files, ["test_dir/test_file3", "test_file"])
        self.assertEqual(sorted(self.scm.changed_files_for_revision(3)), sorted(["test_file", "test_file2"])) # Git and SVN return different orders.
        self.assertEqual(self.scm.changed_files_for_revision(4), ["test_file"])

    def _shared_test_contents_at_revision(self):
        self.assertEqual(self.scm.contents_at_revision("test_file", 2), "test1test2")
        self.assertEqual(self.scm.contents_at_revision("test_file", 3), "test1test2test3\n")
        self.assertEqual(self.scm.contents_at_revision("test_file", 4), "test1test2test3\ntest4\n")

        self.assertEqual(self.scm.contents_at_revision("test_file2", 3), "second file")
        # Files which don't exist:
        # Currently we raise instead of returning None because detecting the difference between
        # "file not found" and any other error seems impossible with svn (git seems to expose such through the return code).
        self.assertRaises(ScriptError, self.scm.contents_at_revision, "test_file2", 2)
        self.assertRaises(ScriptError, self.scm.contents_at_revision, "does_not_exist", 2)

    def _shared_test_committer_email_for_revision(self):
        self.assertEqual(self.scm.committer_email_for_revision(2), getpass.getuser()) # Committer "email" will be the current user

    def _shared_test_reverse_diff(self):
        self._setup_webkittools_scripts_symlink(self.scm) # Git's apply_reverse_diff uses resolve-ChangeLogs
        # Only test the simple case, as any other will end up with conflict markers.
        self.scm.apply_reverse_diff('4')
        self.assertEqual(read_from_path('test_file'), "test1test2test3\n")

    def _shared_test_diff_for_revision(self):
        # Patch formats are slightly different between svn and git, so just regexp for things we know should be there.
        r3_patch = self.scm.diff_for_revision(3)
        self.assertTrue(re.search('test3', r3_patch))
        self.assertFalse(re.search('test4', r3_patch))
        self.assertTrue(re.search('test2', r3_patch))
        self.assertTrue(re.search('test2', self.scm.diff_for_revision(2)))

    def _shared_test_svn_apply_git_patch(self):
        self._setup_webkittools_scripts_symlink(self.scm)
        git_binary_addition = """diff --git a/fizzbuzz7.gif b/fizzbuzz7.gif
new file mode 100644
index 0000000000000000000000000000000000000000..64a9532e7794fcd791f6f12157406d90
60151690
GIT binary patch
literal 512
zcmZ?wbhEHbRAx|MU|?iW{Kxc~?KofD;ckY;H+&5HnHl!!GQMD7h+sU{_)e9f^V3c?
zhJP##HdZC#4K}7F68@!1jfWQg2daCm-gs#3|JREDT>c+pG4L<_2;w##WMO#ysPPap
zLqpAf1OE938xAsSp4!5f-o><?VKe(#0jEcwfHGF4%M1^kRs14oVBp2ZEL{E1N<-zJ
zsfLmOtKta;2_;2c#^S1-8cf<nb!QnGl>c!Xe6RXvrEtAWBvSDTgTO1j3vA31Puw!A
zs(87q)j_mVDTqBo-P+03-P5mHCEnJ+x}YdCuS7#bCCyePUe(ynK+|4b-3qK)T?Z&)
zYG+`tl4h?GZv_$t82}X4*DTE|$;{DEiPyF@)U-1+FaX++T9H{&%cag`W1|zVP@`%b
zqiSkp6{BTpWTkCr!=<C6Q=?#~R8^JfrliAF6Q^gV9Iup8RqCXqqhqC`qsyhk<-nlB
z00f{QZvfK&|Nm#oZ0TQl`Yr$BIa6A@16O26ud7H<QM=xl`toLKnz-3h@9c9q&wm|X
z{89I|WPyD!*M?gv?q`;L=2YFeXrJQNti4?}s!zFo=5CzeBxC69xA<zrjP<wUcCRh4
ptUl-ZG<%a~#LwkIWv&q!KSCH7tQ8cJDiw+|GV?MN)RjY50RTb-xvT&H

literal 0
HcmV?d00001

"""
        self.checkout.apply_patch(self._create_patch(git_binary_addition))
        added = read_from_path('fizzbuzz7.gif', encoding=None)
        self.assertEqual(512, len(added))
        self.assertTrue(added.startswith('GIF89a'))
        self.assertTrue('fizzbuzz7.gif' in self.scm.changed_files())

        # The file already exists.
        self.assertRaises(ScriptError, self.checkout.apply_patch, self._create_patch(git_binary_addition))

        git_binary_modification = """diff --git a/fizzbuzz7.gif b/fizzbuzz7.gif
index 64a9532e7794fcd791f6f12157406d9060151690..323fae03f4606ea9991df8befbb2fca7
GIT binary patch
literal 7
OcmYex&reD$;sO8*F9L)B

literal 512
zcmZ?wbhEHbRAx|MU|?iW{Kxc~?KofD;ckY;H+&5HnHl!!GQMD7h+sU{_)e9f^V3c?
zhJP##HdZC#4K}7F68@!1jfWQg2daCm-gs#3|JREDT>c+pG4L<_2;w##WMO#ysPPap
zLqpAf1OE938xAsSp4!5f-o><?VKe(#0jEcwfHGF4%M1^kRs14oVBp2ZEL{E1N<-zJ
zsfLmOtKta;2_;2c#^S1-8cf<nb!QnGl>c!Xe6RXvrEtAWBvSDTgTO1j3vA31Puw!A
zs(87q)j_mVDTqBo-P+03-P5mHCEnJ+x}YdCuS7#bCCyePUe(ynK+|4b-3qK)T?Z&)
zYG+`tl4h?GZv_$t82}X4*DTE|$;{DEiPyF@)U-1+FaX++T9H{&%cag`W1|zVP@`%b
zqiSkp6{BTpWTkCr!=<C6Q=?#~R8^JfrliAF6Q^gV9Iup8RqCXqqhqC`qsyhk<-nlB
z00f{QZvfK&|Nm#oZ0TQl`Yr$BIa6A@16O26ud7H<QM=xl`toLKnz-3h@9c9q&wm|X
z{89I|WPyD!*M?gv?q`;L=2YFeXrJQNti4?}s!zFo=5CzeBxC69xA<zrjP<wUcCRh4
ptUl-ZG<%a~#LwkIWv&q!KSCH7tQ8cJDiw+|GV?MN)RjY50RTb-xvT&H

"""
        self.checkout.apply_patch(self._create_patch(git_binary_modification))
        modified = read_from_path('fizzbuzz7.gif', encoding=None)
        self.assertEqual('foobar\n', modified)
        self.assertTrue('fizzbuzz7.gif' in self.scm.changed_files())

        # Applying the same modification should fail.
        self.assertRaises(ScriptError, self.checkout.apply_patch, self._create_patch(git_binary_modification))

        git_binary_deletion = """diff --git a/fizzbuzz7.gif b/fizzbuzz7.gif
deleted file mode 100644
index 323fae0..0000000
GIT binary patch
literal 0
HcmV?d00001

literal 7
OcmYex&reD$;sO8*F9L)B

"""
        self.checkout.apply_patch(self._create_patch(git_binary_deletion))
        self.assertFalse(os.path.exists('fizzbuzz7.gif'))
        self.assertFalse('fizzbuzz7.gif' in self.scm.changed_files())

        # Cannot delete again.
        self.assertRaises(ScriptError, self.checkout.apply_patch, self._create_patch(git_binary_deletion))


class SVNTest(SCMTest):

    @staticmethod
    def _set_date_and_reviewer(changelog_entry):
        # Joe Cool matches the reviewer set in SCMTest._create_patch
        changelog_entry = changelog_entry.replace('REVIEWER_HERE', 'Joe Cool')
        # svn-apply will update ChangeLog entries with today's date.
        return changelog_entry.replace('DATE_HERE', date.today().isoformat())

    def test_svn_apply(self):
        first_entry = """2009-10-26  Eric Seidel  <eric@webkit.org>

        Reviewed by Foo Bar.

        Most awesome change ever.

        * scm_unittest.py:
"""
        intermediate_entry = """2009-10-27  Eric Seidel  <eric@webkit.org>

        Reviewed by Baz Bar.

        A more awesomer change yet!

        * scm_unittest.py:
"""
        one_line_overlap_patch = """Index: ChangeLog
===================================================================
--- ChangeLog	(revision 5)
+++ ChangeLog	(working copy)
@@ -1,5 +1,13 @@
 2009-10-26  Eric Seidel  <eric@webkit.org>
 
+        Reviewed by NOBODY (OOPS!).
+
+        Second most awesome change ever.
+
+        * scm_unittest.py:
+
+2009-10-26  Eric Seidel  <eric@webkit.org>
+
         Reviewed by Foo Bar.
 
         Most awesome change ever.
"""
        one_line_overlap_entry = """DATE_HERE  Eric Seidel  <eric@webkit.org>

        Reviewed by REVIEWER_HERE.

        Second most awesome change ever.

        * scm_unittest.py:
"""
        two_line_overlap_patch = """Index: ChangeLog
===================================================================
--- ChangeLog	(revision 5)
+++ ChangeLog	(working copy)
@@ -2,6 +2,14 @@
 
         Reviewed by Foo Bar.
 
+        Second most awesome change ever.
+
+        * scm_unittest.py:
+
+2009-10-26  Eric Seidel  <eric@webkit.org>
+
+        Reviewed by Foo Bar.
+
         Most awesome change ever.
 
         * scm_unittest.py:
"""
        two_line_overlap_entry = """DATE_HERE  Eric Seidel  <eric@webkit.org>

        Reviewed by Foo Bar.

        Second most awesome change ever.

        * scm_unittest.py:
"""
        write_into_file_at_path('ChangeLog', first_entry)
        run_command(['svn', 'add', 'ChangeLog'])
        run_command(['svn', 'commit', '--quiet', '--message', 'ChangeLog commit'])

        # Patch files were created against just 'first_entry'.
        # Add a second commit to make svn-apply have to apply the patches with fuzz.
        changelog_contents = "%s\n%s" % (intermediate_entry, first_entry)
        write_into_file_at_path('ChangeLog', changelog_contents)
        run_command(['svn', 'commit', '--quiet', '--message', 'Intermediate commit'])

        self._setup_webkittools_scripts_symlink(self.scm)
        self.checkout.apply_patch(self._create_patch(one_line_overlap_patch))
        expected_changelog_contents = "%s\n%s" % (self._set_date_and_reviewer(one_line_overlap_entry), changelog_contents)
        self.assertEquals(read_from_path('ChangeLog'), expected_changelog_contents)

        self.scm.revert_files(['ChangeLog'])
        self.checkout.apply_patch(self._create_patch(two_line_overlap_patch))
        expected_changelog_contents = "%s\n%s" % (self._set_date_and_reviewer(two_line_overlap_entry), changelog_contents)
        self.assertEquals(read_from_path('ChangeLog'), expected_changelog_contents)

    def setUp(self):
        SVNTestRepository.setup(self)
        os.chdir(self.svn_checkout_path)
        self.scm = detect_scm_system(self.svn_checkout_path)
        # For historical reasons, we test some checkout code here too.
        self.checkout = Checkout(self.scm)

    def tearDown(self):
        SVNTestRepository.tear_down(self)

    def test_create_patch_is_full_patch(self):
        test_dir_path = os.path.join(self.svn_checkout_path, "test_dir2")
        os.mkdir(test_dir_path)
        test_file_path = os.path.join(test_dir_path, 'test_file2')
        write_into_file_at_path(test_file_path, 'test content')
        run_command(['svn', 'add', 'test_dir2'])

        # create_patch depends on 'svn-create-patch', so make a dummy version.
        scripts_path = os.path.join(self.svn_checkout_path, 'WebKitTools', 'Scripts')
        os.makedirs(scripts_path)
        create_patch_path = os.path.join(scripts_path, 'svn-create-patch')
        write_into_file_at_path(create_patch_path, '#!/bin/sh\necho $PWD') # We could pass -n to prevent the \n, but not all echo accept -n.
        os.chmod(create_patch_path, stat.S_IXUSR | stat.S_IRUSR)

        # Change into our test directory and run the create_patch command.
        os.chdir(test_dir_path)
        scm = detect_scm_system(test_dir_path)
        self.assertEqual(scm.checkout_root, self.svn_checkout_path) # Sanity check that detection worked right.
        patch_contents = scm.create_patch()
        # Our fake 'svn-create-patch' returns $PWD instead of a patch, check that it was executed from the root of the repo.
        self.assertEqual("%s\n" % os.path.realpath(scm.checkout_root), patch_contents) # Add a \n because echo adds a \n.

    def test_detection(self):
        scm = detect_scm_system(self.svn_checkout_path)
        self.assertEqual(scm.display_name(), "svn")
        self.assertEqual(scm.supports_local_commits(), False)

    def test_apply_small_binary_patch(self):
        patch_contents = """Index: test_file.swf
===================================================================
Cannot display: file marked as a binary type.
svn:mime-type = application/octet-stream

Property changes on: test_file.swf
___________________________________________________________________
Name: svn:mime-type
   + application/octet-stream


Q1dTBx0AAAB42itg4GlgYJjGwMDDyODMxMDw34GBgQEAJPQDJA==
"""
        expected_contents = base64.b64decode("Q1dTBx0AAAB42itg4GlgYJjGwMDDyODMxMDw34GBgQEAJPQDJA==")
        self._setup_webkittools_scripts_symlink(self.scm)
        patch_file = self._create_patch(patch_contents)
        self.checkout.apply_patch(patch_file)
        actual_contents = read_from_path("test_file.swf", encoding=None)
        self.assertEqual(actual_contents, expected_contents)

    def test_apply_svn_patch(self):
        scm = detect_scm_system(self.svn_checkout_path)
        patch = self._create_patch(run_command(['svn', 'diff', '-r4:3']))
        self._setup_webkittools_scripts_symlink(scm)
        Checkout(scm).apply_patch(patch)

    def test_apply_svn_patch_force(self):
        scm = detect_scm_system(self.svn_checkout_path)
        patch = self._create_patch(run_command(['svn', 'diff', '-r2:4']))
        self._setup_webkittools_scripts_symlink(scm)
        self.assertRaises(ScriptError, Checkout(scm).apply_patch, patch, force=True)

    def test_commit_logs(self):
        # Commits have dates and usernames in them, so we can't just direct compare.
        self.assertTrue(re.search('fourth commit', self.scm.last_svn_commit_log()))
        self.assertTrue(re.search('second commit', self.scm.svn_commit_log(2)))

    def test_commit_text_parsing(self):
        self._shared_test_commit_with_message()

    def test_commit_with_username(self):
        self._shared_test_commit_with_message("dbates@webkit.org")

    def test_has_authorization_for_realm(self):
        scm = detect_scm_system(self.svn_checkout_path)
        fake_home_dir = tempfile.mkdtemp(suffix="fake_home_dir")
        svn_config_dir_path = os.path.join(fake_home_dir, ".subversion")
        os.mkdir(svn_config_dir_path)
        fake_webkit_auth_file = os.path.join(svn_config_dir_path, "fake_webkit_auth_file")
        write_into_file_at_path(fake_webkit_auth_file, SVN.svn_server_realm)
        self.assertTrue(scm.has_authorization_for_realm(home_directory=fake_home_dir))
        os.remove(fake_webkit_auth_file)
        os.rmdir(svn_config_dir_path)
        os.rmdir(fake_home_dir)

    def test_not_have_authorization_for_realm(self):
        scm = detect_scm_system(self.svn_checkout_path)
        fake_home_dir = tempfile.mkdtemp(suffix="fake_home_dir")
        svn_config_dir_path = os.path.join(fake_home_dir, ".subversion")
        os.mkdir(svn_config_dir_path)
        self.assertFalse(scm.has_authorization_for_realm(home_directory=fake_home_dir))
        os.rmdir(svn_config_dir_path)
        os.rmdir(fake_home_dir)

    def test_reverse_diff(self):
        self._shared_test_reverse_diff()

    def test_diff_for_revision(self):
        self._shared_test_diff_for_revision()

    def test_svn_apply_git_patch(self):
        self._shared_test_svn_apply_git_patch()

    def test_changed_files(self):
        self._shared_test_changed_files()

    def test_changed_files_for_revision(self):
        self._shared_test_changed_files_for_revision()

    def test_added_files(self):
        self._shared_test_added_files()

    def test_contents_at_revision(self):
        self._shared_test_contents_at_revision()

    def test_committer_email_for_revision(self):
        self._shared_test_committer_email_for_revision()


class GitTest(SCMTest):

    def _setup_git_clone_of_svn_repository(self):
        self.git_checkout_path = tempfile.mkdtemp(suffix="git_test_checkout")
        # --quiet doesn't make git svn silent, so we use run_silent to redirect output
        run_silent(['git', 'svn', '--quiet', 'clone', self.svn_repo_url, self.git_checkout_path])

    def _tear_down_git_clone_of_svn_repository(self):
        run_command(['rm', '-rf', self.git_checkout_path])

    def setUp(self):
        SVNTestRepository.setup(self)
        self._setup_git_clone_of_svn_repository()
        os.chdir(self.git_checkout_path)
        self.scm = detect_scm_system(self.git_checkout_path)
        # For historical reasons, we test some checkout code here too.
        self.checkout = Checkout(self.scm)

    def tearDown(self):
        SVNTestRepository.tear_down(self)
        self._tear_down_git_clone_of_svn_repository()

    def test_detection(self):
        scm = detect_scm_system(self.git_checkout_path)
        self.assertEqual(scm.display_name(), "git")
        self.assertEqual(scm.supports_local_commits(), True)

    def test_read_git_config(self):
        key = 'test.git-config'
        value = 'git-config value'
        run_command(['git', 'config', key, value])
        self.assertEqual(self.scm.read_git_config(key), value)

    def test_local_commits(self):
        test_file = os.path.join(self.git_checkout_path, 'test_file')
        write_into_file_at_path(test_file, 'foo')
        run_command(['git', 'commit', '-a', '-m', 'local commit'])

        self.assertEqual(len(self.scm.local_commits()), 1)

    def test_discard_local_commits(self):
        test_file = os.path.join(self.git_checkout_path, 'test_file')
        write_into_file_at_path(test_file, 'foo')
        run_command(['git', 'commit', '-a', '-m', 'local commit'])

        self.assertEqual(len(self.scm.local_commits()), 1)
        self.scm.discard_local_commits()
        self.assertEqual(len(self.scm.local_commits()), 0)

    def test_delete_branch(self):
        old_branch = run_command(['git', 'symbolic-ref', 'HEAD']).strip()
        new_branch = 'foo'

        run_command(['git', 'checkout', '-b', new_branch])
        self.assertEqual(run_command(['git', 'symbolic-ref', 'HEAD']).strip(), 'refs/heads/' + new_branch)

        run_command(['git', 'checkout', old_branch])
        self.scm.delete_branch(new_branch)

        self.assertFalse(re.search(r'foo', run_command(['git', 'branch'])))

    def test_svn_merge_base(self):
        # Diff to merge-base should include working-copy changes,
        # which the diff to svn_branch.. doesn't.
        test_file = os.path.join(self.git_checkout_path, 'test_file')
        write_into_file_at_path(test_file, 'foo')

        diff_to_common_base = run_command(['git', 'diff', self.scm.svn_branch_name() + '..'])
        diff_to_merge_base = run_command(['git', 'diff', self.scm.svn_merge_base()])

        self.assertFalse(re.search(r'foo', diff_to_common_base))
        self.assertTrue(re.search(r'foo', diff_to_merge_base))

    def test_rebase_in_progress(self):
        svn_test_file = os.path.join(self.svn_checkout_path, 'test_file')
        write_into_file_at_path(svn_test_file, "svn_checkout")
        run_command(['svn', 'commit', '--message', 'commit to conflict with git commit'], cwd=self.svn_checkout_path)

        git_test_file = os.path.join(self.git_checkout_path, 'test_file')
        write_into_file_at_path(git_test_file, "git_checkout")
        run_command(['git', 'commit', '-a', '-m', 'commit to be thrown away by rebase abort'])

        # --quiet doesn't make git svn silent, so use run_silent to redirect output
        self.assertRaises(ScriptError, run_silent, ['git', 'svn', '--quiet', 'rebase']) # Will fail due to a conflict leaving us mid-rebase.

        scm = detect_scm_system(self.git_checkout_path)
        self.assertTrue(scm.rebase_in_progress())

        # Make sure our cleanup works.
        scm.clean_working_directory()
        self.assertFalse(scm.rebase_in_progress())

        # Make sure cleanup doesn't throw when no rebase is in progress.
        scm.clean_working_directory()

    def test_commitish_parsing(self):
        scm = detect_scm_system(self.git_checkout_path)
    
        # Multiple revisions are cherry-picked.
        self.assertEqual(len(scm.commit_ids_from_commitish_arguments(['HEAD~2'])), 1)
        self.assertEqual(len(scm.commit_ids_from_commitish_arguments(['HEAD', 'HEAD~2'])), 2)
    
        # ... is an invalid range specifier
        self.assertRaises(ScriptError, scm.commit_ids_from_commitish_arguments, ['trunk...HEAD'])

    def test_commitish_order(self):
        scm = detect_scm_system(self.git_checkout_path)

        commit_range = 'HEAD~3..HEAD'

        actual_commits = scm.commit_ids_from_commitish_arguments([commit_range])
        expected_commits = []
        expected_commits += reversed(run_command(['git', 'rev-list', commit_range]).splitlines())

        self.assertEqual(actual_commits, expected_commits)

    def test_apply_git_patch(self):
        scm = detect_scm_system(self.git_checkout_path)
        # We carefullly pick a diff which does not have a directory addition
        # as currently svn-apply will error out when trying to remove directories
        # in Git: https://bugs.webkit.org/show_bug.cgi?id=34871
        patch = self._create_patch(run_command(['git', 'diff', 'HEAD..HEAD^']))
        self._setup_webkittools_scripts_symlink(scm)
        Checkout(scm).apply_patch(patch)

    def test_apply_git_patch_force(self):
        scm = detect_scm_system(self.git_checkout_path)
        patch = self._create_patch(run_command(['git', 'diff', 'HEAD~2..HEAD']))
        self._setup_webkittools_scripts_symlink(scm)
        self.assertRaises(ScriptError, Checkout(scm).apply_patch, patch, force=True)

    def test_commit_text_parsing(self):
        self._shared_test_commit_with_message()

    def test_reverse_diff(self):
        self._shared_test_reverse_diff()

    def test_diff_for_revision(self):
        self._shared_test_diff_for_revision()

    def test_svn_apply_git_patch(self):
        self._shared_test_svn_apply_git_patch()

    def test_create_binary_patch(self):
        # Create a git binary patch and check the contents.
        scm = detect_scm_system(self.git_checkout_path)
        test_file_name = 'binary_file'
        test_file_path = os.path.join(self.git_checkout_path, test_file_name)
        file_contents = ''.join(map(chr, range(256)))
        write_into_file_at_path(test_file_path, file_contents, encoding=None)
        run_command(['git', 'add', test_file_name])
        patch = scm.create_patch()
        self.assertTrue(re.search(r'\nliteral 0\n', patch))
        self.assertTrue(re.search(r'\nliteral 256\n', patch))

        # Check if we can apply the created patch.
        run_command(['git', 'rm', '-f', test_file_name])
        self._setup_webkittools_scripts_symlink(scm)
        self.checkout.apply_patch(self._create_patch(patch))
        self.assertEqual(file_contents, read_from_path(test_file_path, encoding=None))

        # Check if we can create a patch from a local commit.
        write_into_file_at_path(test_file_path, file_contents, encoding=None)
        run_command(['git', 'add', test_file_name])
        run_command(['git', 'commit', '-m', 'binary diff'])
        patch_from_local_commit = scm.create_patch_from_local_commit('HEAD')
        self.assertTrue(re.search(r'\nliteral 0\n', patch_from_local_commit))
        self.assertTrue(re.search(r'\nliteral 256\n', patch_from_local_commit))
        patch_since_local_commit = scm.create_patch_since_local_commit('HEAD^1')
        self.assertTrue(re.search(r'\nliteral 0\n', patch_since_local_commit))
        self.assertTrue(re.search(r'\nliteral 256\n', patch_since_local_commit))
        self.assertEqual(patch_from_local_commit, patch_since_local_commit)

    def test_changed_files(self):
        self._shared_test_changed_files()

    def test_changed_files_for_revision(self):
        self._shared_test_changed_files_for_revision()

    def test_contents_at_revision(self):
        self._shared_test_contents_at_revision()

    def test_added_files(self):
        self._shared_test_added_files()

    def test_committer_email_for_revision(self):
        self._shared_test_committer_email_for_revision()


if __name__ == '__main__':
    unittest.main()
