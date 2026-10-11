# DocuGit

DocuGit is a small, local desktop app for keeping named versions of Word and Excel documents. It uses a dark Tkinter interface, SQLite metadata, and immutable file snapshots. No Git installation or network connection is required.

## Run

```powershell
python -m pip install -r requirements.txt
python main.py
```

Python 3.10 or later is recommended. Tkinter is included with most Windows Python installations.

## Use

1. Choose **Add document** and select a `.docx` or `.xlsx` file. DocuGit keeps the original where it is and copies a tracked working copy into `documents/`.
2. Use the **Edit** tab for text and cell-value edits; edits are saved to the tracked copy automatically. For full Word/Excel editing, choose **Open working copy** and edit the file in its normal desktop application.
3. Enter a commit title and choose **Commit working copy**. DocuGit snapshots the tracked copy directly; it does not ask you to select the file again. Unchanged files cannot create duplicate commits.
4. Choose **Publish** to commit any remaining edits, archive the previous original under `.docugit/published-backups/`, and replace the original at its existing location. Publishing is confirmed first. Older documents imported before original-path tracking can use **Link original** once.
5. Select versions in the history. **Compare** compares two selected versions, or the selected version with its direct predecessor. **Restore selected** restores its contents as a new, timestamped version.

DOCX paragraphs and tables, and XLSX sheet cell values, are shown in the in-app preview and text diff. The Edit tab changes paragraph text and existing table values, or existing worksheet cell values; it does not add/remove paragraphs, rows, sheets, or other document structure. Use **Open working copy** for formatting and structural changes. The author is currently hardcoded to `Bhavya` in `docugit/ui.py`; change `AUTHOR_NAME` there to stamp another local user on new commits.

## Repository layout

- `documents/` contains the current working copies.
- `.docugit/docugit.sqlite3` stores document names, version numbers, commit titles, authors, timestamps, and SHA-256 checksums.
- `.docugit/objects/` contains the immutable file snapshot for each version.
- `.docugit/published-backups/` contains the original files replaced by Publish.

Keep `.docugit/` when backing up or moving a repository. Removing it deletes the version history; `documents/` alone contains only the current copies.

## Tests

```powershell
python -m unittest discover -s tests -v
```