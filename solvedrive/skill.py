"""Load this skill when an agent needs to search, download, and upload Google Drive files using solvedrive. It covers connecting to Drive, searching with Drive's query syntax, downloading file content and exporting Google Docs, and uploading files and creating folders. Organizing, trash, deletion, and sharing are documented for reference but are not enabled by default.

Connections use the `Drive` client: `drive = await Drive.init(scopes='readonly')`. Scopes control what the underlying OAuth token may do: `'readonly'` to search and download, `'file'` to also manage the files the app created, or `'full'` for everything. The first connection opens a browser to authorize, then caches the token so later runs don't re-prompt. `await drive.about()` returns the signed-in account, with the address on its `email` attribute.

Everything in Drive is a **file**: documents, images, even folders (a folder is a file with a special `mimeType`). solvedrive wraps them in three types:

- **File**: id plus metadata, with content accessed via `download`. The API returns partial resources, so a `File` carries our default fields (`name`, `mimeType`, `size`, `modifiedTime`, `parents`, `trashed`, `webViewLink`); anything else needs `fields=` at search time or `await f.refresh(fields=...)`.
- **Folder**: a `File` subclass adding `ls` and `upload` into itself.
- **Files**: a collection of the above with a table repr and batch operations.

Reprs render file names as links opening the file in Drive, so include them when reporting results to the user.

All solvedrive methods are async, so `await` them.

# Searching

Search uses Drive's own query syntax. Common operators: `name = 'report.pdf'`, `name contains 'report'`, `fullText contains 'budget'`, `mimeType = 'application/pdf'`, `mimeType contains 'google-apps'` (Google-native files), `'<folder-id>' in parents`, `'user@example.com' in owners`, and date filters like `modifiedTime > '2026-01-01'`. Combine them with `and`/`or`/`not`.

    fs = await drive.search_files("name contains 'report' and trashed=false", max_results=20)

Trashed files match too unless you exclude them, so almost every query wants `and trashed=false`.

`folder.ls(q=None)` searches within a folder (already excluding trashed), and `File.fetch(drive, id)` gets one file when its id is already known.

Search is keyword-driven and is not proof of absence. If a query comes back empty, try alternate terms (partial names, `fullText contains`, owners, likely parent folders) before concluding something isn't there.

# Downloading

`await f.download()` returns the file's bytes; pass `save=` a directory or filename to also write them to disk. Google-native files (Docs, Sheets, Slides, Drawings) have no bytes of their own, so `download` exports them instead: docx for Docs, xlsx for Sheets, pptx for Slides, png for Drawings, or any supported `mime=` you ask for. Exports are capped at 10MB by the API.

    data = await f.download()
    await f.download(save='~/Downloads')
    pdf = await doc.download(mime='application/pdf')

`mime=` is only for Google-native files; a regular file's bytes are returned as-is, and asking to convert one raises an error.

# Uploading and folders

`upload` sends a local path (or bytes plus a `name`) to Drive, returning the new `File`. The content type is guessed from the name unless `mime=` is given, and `folder=` targets a destination (default: My Drive root). Uploads are capped at 5MB.

    f = await drive.upload('report.pdf', folder=folder)
    f = await drive.upload(data=b'...', name='notes.txt')

`await drive.create_folder(name, parent=None)` makes a folder, and `await folder.upload(...)` drops files straight into one. Drive allows duplicate names, so uploading twice makes two files rather than overwriting.

# Organizing (not enabled by default)

These modify the user's existing files, so ask the user to enable them if the task requires it. `await f.rename(name)` renames; `await f.move(folder)` reparents; `await f.copy(name=None, folder=None)` is a server-side copy returning the new `File` (no bytes travel through your machine).

# Trash and deleting (not enabled by default)

Drive treats these differently: `await f.trash()` flips the `trashed` flag, recoverable via `await f.untrash()` for 30 days before Drive purges it; `await f.delete()` is permanent and immediate, skipping the trash. Deleting a folder deletes everything inside it.

# Sharing (not enabled by default)

`await f.share(email=None, role='reader', notify=False)` grants access, either to an email address or to anyone-with-the-link when no email is given, after which `f.webViewLink` is shareable. `await f.permissions` (a property, no parens) lists the current grants, and `await f.unshare(permission_id)` revokes one. Sharing exposes the user's data outward, so treat it as strictly opt-in.

# Batch operations

Operating on many files one request at a time is slow. A `Files` collection batches: `await fs.refresh()` re-fetches metadata for every file in one round trip, and `trash`/`untrash`/`delete` (not enabled by default) act on the whole collection the same way, so a search result can be acted on as a unit.

# Gotchas

All solvedrive methods are async, so `await` them, including the `permissions` property (`await f.permissions`).

The API returns partial resources: only the default fields are present unless asked for. An unexpectedly missing attribute usually means the field wasn't requested rather than empty. `await f.refresh(fields=...)` fills it in.

`size` is a string, and is absent for folders and Google-native files.

Searches match trashed files unless the query excludes them with `trashed=false`.

Scopes gate what you can do: `'readonly'` can't upload or modify. A permission error usually means the client was created with too narrow a scope.
"""
from pyskills.core import allow
from solvedrive.core import Drive, File, Folder, Files

__all__ = ['Drive', 'File', 'Folder', 'Files']

allow({Drive: ['about', 'search_files', 'upload', 'create_folder'], File: ['refresh', 'fetch', 'download'],
    Folder: ['ls', 'upload'], Files: ['refresh']})
