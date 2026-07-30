"""Load this skill when an agent needs to search, download, and upload Google Drive files using solvedrive. It covers connecting to Drive, searching across My Drive and shared drives with Drive's query syntax, downloading file content and exporting Google Docs, and uploading, renaming, moving, and copying files and creating folders. Trash, deletion, and sharing are documented for reference but are not enabled by default.

Connections use the `GDrive` client, constructed from fastgws credentials: `creds = await oauth_creds(scopes=[...], interactive=False)`, then `gd = GDrive(creds)`. Scopes control what the token may do: `https://www.googleapis.com/auth/drive.readonly` to search and download, `https://www.googleapis.com/auth/drive.file` to also manage the files the app created, or `https://www.googleapis.com/auth/drive` for everything. `await gd.about()` returns the signed-in account, with the address on its `email` attribute.

`interactive=False` means only previously authorized tokens can be used. If it fails with a missing or invalid token error, the requested scopes have not been authorized yet. Authorize them with the two-step flow: `auth_url` returns an authorization link; show it to the user and ask them to visit it, approve access, and paste the code it displays back into the chat. Then pass whatever they paste (a bare code or the full redirect URL) to `finish_auth`, which exchanges it, saves the token, and returns the credentials. The code is single-use and PKCE-bound to this kernel's flow state, so relaying it through the chat is safe. `auth_url` requests the union of the saved token's scopes and the requested ones, so re-authorizing never drops existing grants.

    url = auth_url(scopes=['https://www.googleapis.com/auth/drive.readonly'])
    # show `url` to the user; when they reply with the code:
    gd = GDrive(finish_auth(code))

Everything in Drive is a **file**: documents, images, even folders (a folder is a file with a special `mimeType`). Files live in drives: your personal My Drive, plus any shared drives you're a member of. solvedrive wraps the API in a handful of types:

- **GDrive**: the signed-in account, holding auth, `about`, `upload`, `create_folder`, cross-drive `search_files`, and `list_drives`.
- **Drive**: one drive, either My Drive (id `root`) or a shared drive. It reports your `role`, fetches its `root` folder, and scopes `search_files` to its contents.
- **File**: id plus metadata, with content accessed via `download`. The API returns partial resources, so a `File` carries our default fields (`name`, `mimeType`, `size`, `modifiedTime`, `parents`, `trashed`, `webViewLink`); anything else needs `fields=` at search time or `await f.refresh(fields=...)`.
- **Folder**: a `File` subclass adding `ls` and `upload` into itself.
- **Files** and **Drives**: collections of the above with table reprs; `Files` adds batch operations.

Reprs render file names as links opening the file in Drive, so include them when reporting results to the user.

All solvedrive methods are async, so `await` them.

# Searching

Search uses Drive's own query syntax. Common operators: `name = 'report.pdf'`, `name contains 'report'`, `fullText contains 'budget'`, `mimeType = 'application/pdf'`, `mimeType contains 'google-apps'` (Google-native files), `'<folder-id>' in parents`, `'user@example.com' in owners`, and date filters like `modifiedTime > '2026-01-01'`. Combine them with `and`/`or`/`not`.

    fs = await gd.search_files("name contains 'report' and trashed=false", max_results=20)

`gd.search_files` covers every drive you can see. To search one drive, take a `Drive` from `list_drives` and call its `search_files`. My Drive's scope is the `user` corpus, which also includes files shared directly with you, since the API offers no My-Drive-only scope.

Trashed files match too unless you exclude them, so almost every query wants `and trashed=false`.

`folder.ls(q=None)` searches within a folder (already excluding trashed), and `File.fetch(gd, id)` gets one file when its id is already known.

Search is keyword-driven and is not proof of absence. If a query comes back empty, try alternate terms (partial names, `fullText contains`, owners, likely parent folders) before concluding something isn't there.

# Downloading

`await f.download()` returns the file's bytes; pass `save=` a directory or filename to also write them to disk. Google-native files (Docs, Sheets, Slides, Drawings) have no bytes of their own, so `download` exports them instead: docx for Docs, xlsx for Sheets, pptx for Slides, png for Drawings, or any supported `mime=` you ask for. Exports are capped at 10MB by the API.

    data = await f.download()
    await f.download(save='~/Downloads')
    pdf = await doc.download(mime='application/pdf')

`mime=` is only for Google-native files; a regular file's bytes are returned as-is, and asking to convert one raises an error.

# Uploading and folders

`upload` sends a local path (or bytes plus a `name`) to Drive, returning the new `File`. The content type is guessed from the name unless `mime=` is given, and `folder=` targets a destination (default: My Drive root). Uploads are capped at 5MB.

    f = await gd.upload('report.pdf', folder=folder)
    f = await gd.upload(data=b'...', name='notes.txt')

`await gd.create_folder(name, parent=None)` makes a folder, and `await folder.upload(...)` drops files straight into one. Drive allows duplicate names, so uploading twice makes two files rather than overwriting.

# Drives

`await gd.list_drives()` returns a `Drives` table: My Drive first (id `root`, role `owner`), then every shared drive you're a member of. A shared drive belongs to an organization rather than a person. Members hold one role each on the whole drive (`organizer`, `fileOrganizer`, `writer`, `commenter`, or `reader`), files have no owner, and `d.role` reports yours. `await d.root` is an ordinary `Folder`, so its `upload` and `ls` work inside a shared drive like anywhere else. Creating, deleting, and administering shared drives is not wrapped; the raw client (`gd.drives`) reaches those endpoints if the user asks for them.

# Organizing

`await f.rename(name)` renames; `await f.move(folder)` reparents; `await f.copy(name=None, folder=None)` is a server-side copy returning the new `File` (no bytes travel through your machine). Like `upload`, these are write operations enabled by default: they create or reorganize, but never destroy content. Only destructive operations (trash, deletion, sharing) are disabled by default.

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

Scopes gate what you can do: a `drive.readonly` token can't upload or modify. A permission error usually means the creds were made with too narrow a scope.

Changes propagate with a small delay: a fresh upload or drive can be missing from a listing or search for a moment, so retry briefly before concluding it's absent.
"""
from pyskills.core import allow
from solvedrive.core import GDrive, Drive, File, Folder, Files, Drives
from fastgws.auth import oauth_creds, auth_url, finish_auth

__all__ = ['GDrive', 'Drive', 'File', 'Folder', 'Files', 'Drives', 'oauth_creds', 'auth_url', 'finish_auth']

allow(oauth_creds, auth_url, finish_auth,
      {GDrive: ['__init__', 'about', 'search_files', 'upload', 'create_folder', 'list_drives'], Drive: ['search_files'],
    File: ['refresh', 'fetch', 'download', 'rename', 'move', 'copy'], Folder: ['ls', 'upload'], Files: ['refresh']})
