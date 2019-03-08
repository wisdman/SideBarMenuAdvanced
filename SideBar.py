import os
import shutil
import sublime
import sublime_plugin
import threading

from functools import partial

class SideBarCommand(sublime_plugin.WindowCommand):
  def copy_to_clipboard(self, data):
    sublime.set_clipboard(data)
    lines = len(data.split('\n'))
    self.window.status_message('Copied {} to clipboard'.format(
      '{} lines'.format(lines) if lines > 1 else '"{}"'.format(data)
    ))

  def get_path(self, paths):
    try:
      return paths[0]
    except IndexError:
      return self.window.active_view().file_name()

  @staticmethod
  def retarget_view(source, destination):
    source = os.path.normcase(os.path.abspath(source))
    destination = os.path.normcase(os.path.abspath(destination))
    for window in sublime.windows():
      for view in window.views():
        path = os.path.abspath(view.file_name())
        if os.path.normcase(path) == source:
          view.retarget(destination)

  @staticmethod
  def retarget_all_views(source, destination):
    if source[-1] != os.path.sep:
      source += os.path.sep

    if destination[-1] != os.path.sep:
      destination += os.path.sep

    for window in sublime.windows():
      for view in window.views():
        filename = view.file_name()
        if os.path.commonprefix([source, filename]) == source:
          view.retarget(os.path.join(destination, filename[len(source):]))


class MultipleFilesMixin(object):
  def get_paths(self, paths):
    return paths or [self.get_path(paths)]


class SideBarMenuNewFileCommand(SideBarCommand):
  def run(self, paths):
    base = self.get_path(paths)
    if os.path.isfile(base):
      base = os.path.dirname(base)

    self.window.show_input_panel('File Name:', "", partial(self.on_done, base), None, None)

  def on_done(self, base, leaf):
    if not leaf:
      return

    new = os.path.join(base, leaf)

    try:
      if os.path.exists(new):
        raise OSError("File or Folder already exists")

      base = os.path.dirname(new)
      if not os.path.exists(base):
        os.makedirs(base)

      with open(new, "w+", encoding="utf8", newline="") as f:
        f.write(str(""))

      self.window.open_file(new)

    except OSError as error:
      self.window.status_message('Unable to create file: "{}"'.format(error))
    except:
      self.window.status_message('Unable to create file: "{}"'.format(new))

  def description(self):
    return 'New File'


class SideBarMenuNewFolderCommand(SideBarCommand):
  def run(self, paths):
    base = self.get_path(paths)
    if os.path.isfile(base):
      base = os.path.dirname(base)

    self.window.show_input_panel('Folder Name:', "", partial(self.on_done, base), None, None)

  def on_done(self, base, leaf):
    if not leaf:
      return

    new = os.path.join(base, leaf)

    try:
      os.makedirs(new)

    except OSError as error:
      self.window.status_message('Unable to create folder: "{}"'.format(error))
    except:
      self.window.status_message('Unable to create folder: "{}"'.format(new))

  def description(self):
    return 'New Folder'


class SideBarMenuCopyNameCommand(MultipleFilesMixin, SideBarCommand):
  def run(self, paths):
    leafs = (os.path.split(path)[1] for path in self.get_paths(paths))
    self.copy_to_clipboard('\n'.join(leafs))

  def description(self):
    return 'Copy Filename'


class SideBarMenuCopyRelativePathCommand(MultipleFilesMixin, SideBarCommand):
  def run(self, paths):
    paths = self.get_paths(paths)
    root_paths = self.window.folders()
    relative_paths = []

    for path in paths:
      if not root_paths:
        relative_paths.append(os.path.basename(path))
      else:
        for root in root_paths:
          if path.startswith(root):
            p = os.path.relpath(path, root)
            relative_paths.append(p)
            break

    if not relative_paths:
      relative_paths.append(os.path.basename(path))

    self.copy_to_clipboard('\n'.join(relative_paths))

  def description(self):
    return 'Copy Relative Path'


class SideBarMenuCopyAbsolutePathCommand(MultipleFilesMixin, SideBarCommand):
  def run(self, paths):
    paths = self.get_paths(paths)
    self.copy_to_clipboard('\n'.join(paths))

  def description(self):
    return 'Copy Absolute Path'


class SideBarMenuRenameCommand(SideBarCommand):
  def run(self, paths):
    source = self.get_path(paths)
    base, leaf = os.path.split(source)
    name, _ = os.path.splitext(leaf)

    input_panel = self.window.show_input_panel("New Name:", leaf, partial(self.on_done, source, base), None, None)
    input_panel.sel().clear()
    input_panel.sel().add(sublime.Region(0, len(name)))

  def on_done(self, source, base, leaf):
    new = os.path.join(base, leaf)

    if new == source:
      return

    try:
      if os.path.exists(new):
        raise OSError("File or Folred already exists")

      base = os.path.dirname(new)
      if not os.path.exists(base):
        os.makedirs(base)

      os.rename(source, new)

      if os.path.isfile(new):
        self.retarget_view(source, new)
      else:
        self.retarget_all_views(source, new)

    except OSError as error:
      self.window.status_message('Unable to rename: "{}" to "{}". {}'.format(source, new, error))
    except:
      self.window.status_message('Unable to rename: "{}" to "{}"'.format(source, new))

  def description(self):
    return 'Rename...'


class SideBarMenuDuplicateCommand(SideBarCommand):
  def run(self, paths = []):
    source = self.get_path(paths)
    base, leaf = os.path.split(source)

    name, ext = os.path.splitext(leaf)
    if ext is not '':
      while '.' in name:
        name, _ext = os.path.splitext(name)
        ext = _ext + ext
        if _ext is '':
          break

    input_panel = self.window.show_input_panel('Duplicate as:', source, partial(self.on_done, source, base), None, None)
    input_panel.sel().clear()
    input_panel.sel().add(sublime.Region(len(base) + 1, len(source) - len(ext)))

  def on_done(self, source, base, new):
    new = os.path.join(base, new)
    threading.Thread(target = self.copy, args = (source, new)).start()

  def copy(self, source, new):
    self.window.status_message('Copying "{}" to "{}"'.format(source, new))

    try:
      base = os.path.dirname(new)
      if not os.path.exists(base):
        os.makedirs(base)

      if os.path.isdir(source):
        shutil.copytree(source, new)
      else:
        shutil.copy2(source, new)
        self.window.open_file(new)

    except OSError as error:
      self.window.status_message('Unable to duplicate: "{}" to "{}". {error}'.format(source, new, error))
    except:
      self.window.status_message('Unable to duplicate: "{}" to "{}"'.format(source, new))

    self.window.run_command('refresh_folder_list')

  def description(self):
    return 'Duplicate…'


class SideBarMenuMoveCommand(SideBarCommand):
  def run(self, paths):
    source = self.get_path(paths)
    base, leaf = os.path.split(source)
    _, ext = os.path.splitext(leaf)

    input_panel = self.window.show_input_panel('Move to:', source, partial(self.on_done, source), None, None)
    input_panel.sel().clear()
    input_panel.sel().add(sublime.Region(len(base) + 1, len(source) - len(ext)))

  def on_done(self, source, new):
    threading.Thread(target = self.move, args = (source, new)).start()

  def move(self, source, new):
    self.window.status_message('Moving "{}" to "{}"'.format(source, new))

    try:
      base = os.path.dirname(new)
      if not os.path.exists(base):
        os.makedirs(base)

      shutil.move(source, new)

      if os.path.isfile(new):
        self.retarget_view(source, new)
      else:
        self.retarget_all_views(source, new)

    except OSError as error:
      self.window.status_message('Unable to moving: "{}" to "{}". {}'.format(source, new, error))
    except:
      self.window.status_message('Unable to moving: "{}" to "{}"'.format(source, new))

    self.window.run_command('refresh_folder_list')

  def description(self):
    return 'Move…'


class SideBarMenuDeleteCommand(SideBarCommand):
  def run(self, paths):
    if len(paths) == 1:
      message = "Delete %s?" % paths[0]
    else:
      message = "Delete %d items?" % len(paths)

    if sublime.ok_cancel_dialog(message, "Delete"):
      import Default.send2trash as send2trash
      try:
        for path in paths:
          send2trash.send2trash(path)
      except:
        self.window.status_message("Unable to delete")

  def description(self):
    return 'Delete'
