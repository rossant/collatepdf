# collatepdf

A Python script to **collate multiple PDFs into a single PDF**, with:

* automatic TOC generation
* automatic page resizing
* overlay bar incrustation on each page with the current file name and global page number

**Note:** this is a quick-and-dirty, alpha-quality script I wrote for my own needs. Use at your own risks. Please feel free to improve it if you find it useful.

## Structure of the collated PDF

- Optional cover PDF
- Table of contents
- Optional divider pages
- PDF documents

![](screenshots/collatepdf.png)

## Cover and table of contents

![](screenshots/cover.png)

## Optional divider page and first document page with overlay bar

![](screenshots/divider.png)

## Installation

Dependencies:

- Python
- pypdf
- reportlab

Installation instructions:

```bash
git clone https://github.com/rossant/collatepdf.git
cd collatepdf/
pip install -e .
```

## Usage

There are two steps:

- Generate an `index.txt` page from your list of PDF documents to collate, and edit it manually to specify the optional divider pages.
- Generate the collated PDF.

```bash
# Create the index file.
./collatepdf.py makeindex samples/docs/*.pdf -o samples/index.txt

# Generate the collated PDF with a cover PDF.
./collatepdf.py makepdf samples/index.txt -c samples/cover.pdf -o samples/collated.pdf
```
