#!/usr/bin/env python3


"""
A tool to collate multiple PDFs into a single PDF, with automatic TOC generation,
automatic page resizing, and overlay bar incrustation on each page with the current file name and
global page number.

    pip install -r requirements.txt

    # Create the index file.
    ./collatepdf.py makeindex samples/docs/*.pdf -o samples/index.txt

    # Generate the collated PDF with a cover PDF.
    ./collatepdf.py makepdf samples/index.txt -c samples/cover.pdf -o samples/collated.pdf

"""


# -------------------------------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------------------------------

import argparse
from contextlib import contextmanager
import gc
from io import BytesIO
import os
import os.path as op
from pathlib import Path
import sys

from reportlab.pdfgen import canvas
from reportlab.lib.colors import white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from pypdf import PdfReader, PdfWriter, PageObject

# NOTE: weird PDF bugs appear otherwise
gc.disable()


# -------------------------------------------------------------------------------------------------
# Parameters
# -------------------------------------------------------------------------------------------------

class Bunch:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


PARAMS = Bunch()

# PARAMS.root_dir = '.'
PARAMS.page_format = A4  # (8*inch, 10*inch)
PARAMS.index_file = 'samples/index.txt'
PARAMS.output_file = 'samples/collated.pdf'
PARAMS.cover_file = ''  # 'samples/cover.pdf'

# TOC params
PARAMS.toc_title = "Table of contents"
PARAMS.toc_font_size = 12

# Divider params
PARAMS.divider_font_size = 24

# Overlay params
PARAMS.overlay_font_size = 12
PARAMS.overlay_bgcolor = (.3, .6, .9)
PARAMS.overlay_edgecolor = white
PARAMS.overlay_textcolor = (0, 0, 0)
PARAMS.overlay_opacity = 0.9
PARAMS.overlay_w = 500
PARAMS.overlay_h = 20
PARAMS.overlay_x = 0.6 * inch
PARAMS.overlay_y = 11.21 * inch
PARAMS.overlay_x_text = .65 * inch
PARAMS.overlay_y_text = 11.29 * inch

# Other params
PARAMS.font = 'Helvetica'
PARAMS.duplex = True


# -------------------------------------------------------------------------------------------------
# Generic utils
# -------------------------------------------------------------------------------------------------

def append_pdf(output, new):
    if isinstance(new, (str, Path)):
        new = PdfReader(new)
    n = new.get_num_pages()
    for i in range(n):
        output.add_page(new.get_page(i))
    return n


@contextmanager
def make_canvas():
    buffer = BytesIO()
    toc_canvas = canvas.Canvas(buffer, pagesize=PARAMS.page_format)
    try:
        yield toc_canvas
    finally:
        toc_canvas.save()
        buffer.seek(0)
        toc_canvas.pdf = PdfReader(buffer)
        toc_canvas.pdf.buffer = buffer
        toc_canvas.pdf.canvas = toc_canvas


def iter_files(file_paths):
    for file_path in file_paths:
        if file_path.startswith('@'):
            yield file_path, None
        elif not file_path:
            yield None, None
        # elif file_path == "LEFT":
        #     yield "LEFT", None
        else:
            # abs_path = op.join(PARAMS.root_dir, file_path)
            if not op.exists(file_path):
                print(f"********** {file_path} does not exist")
                continue
            print(file_path)
            pdf_reader = PdfReader(file_path)
            yield file_path, pdf_reader


def write_pdf(writer, output_file):
    with open(output_file, 'wb') as f:
        writer.write(f)


def resize_page(page, page_format):
    w, h = page_format
    new_page = PageObject.create_blank_page(width=w, height=h)
    new_page.merge_page(page)
    return new_page


def count_pages(file_paths):
    return sum(
        pdf_reader.get_num_pages()
        for _, pdf_reader in iter_files(file_paths) if pdf_reader)


def get_pretty_name(file_path, replace_slashes=True):
    pretty_name = file_path.replace('./', '')
    if replace_slashes:
        pretty_name = pretty_name.replace('/', ' — ')
    pretty_name = '.'.join(pretty_name.split('.')[:-1])
    return pretty_name


def set_font(font_path):
    font_name = op.basename(font_path)
    PARAMS.font = font_name
    pdfmetrics.registerFont(TTFont(PARAMS.font, font_path))


def ensure_even_pages(writer):
    n = 0
    if PARAMS.duplex and writer.get_num_pages() % 2 == 1:
        writer.add_blank_page()
        n = 1
    assert not PARAMS.duplex or writer.get_num_pages() % 2 == 0
    return n


# -------------------------------------------------------------------------------------------------
# Index
# -------------------------------------------------------------------------------------------------

def make_index(file_paths, index_file):
    pdf_files = [
        f"@ {get_pretty_name(file, replace_slashes=False)}\n{file}\n\n"
        for file in file_paths if file.endswith('.pdf')]

    with open(index_file, 'w') as f:
        f.write(f"# Comments start with #.\n")
        f.write(f"# Empty lines are ignored.\n")
        f.write(f"# Index processing is stopped with `# STOP` on a line.\n")
        f.write(f"# PDF files are included by putting their paths on each line.\n")
        f.write(
            f"# Divider pages are included as follows: `@ Some title / Subtitle below`.\n\n")

        f.writelines(pdf_files)


def parse_index(index_file):
    # index_file = op.join(root_dir, 'index.txt')
    with open(index_file, 'r') as f:
        file_paths = []
        for line in f.readlines():
            line = line.strip()
            if line.startswith("# STOP"):
                break
            if not line:
                continue
            if line == "# BLANK":
                file_paths.append('')
            # if line == "# LEFT":
            #     file_paths.append('LEFT')
            if not line.startswith('#'):
                file_paths.append(line)
            else:  # comment
                if 'PARAMS.' in line:
                    # modify parameters defined as comment in the index file
                    exec(line[1:].strip(), {'PARAMS': PARAMS}, {})
    return file_paths


# -------------------------------------------------------------------------------------------------
# TOC
# -------------------------------------------------------------------------------------------------

def create_toc(canvas, toc):
    canvas.setFont(PARAMS.font, PARAMS.toc_font_size)
    canvas.drawString(1 * inch, 10.5 * inch, PARAMS.toc_title)
    y = 10.25 * inch
    for entry in toc:
        canvas.drawString(1 * inch, y, entry)
        y -= 0.25 * inch


def create_divider(canvas, title):
    lines = title.split('/')

    width, height = PARAMS.page_format
    canvas.setPageSize(PARAMS.page_format)
    canvas.setFont(PARAMS.font, PARAMS.divider_font_size)

    total_height = len(lines) * PARAMS.divider_font_size
    start_y = (height + total_height) / 2

    for i, line in enumerate(lines):
        text_y = start_y - i * PARAMS.divider_font_size * 1.5
        text_width = canvas.stringWidth(
            line, PARAMS.font, PARAMS.divider_font_size)
        text_x = (width - text_width) / 2
        canvas.drawString(text_x, text_y, line)

    canvas.showPage()


# -------------------------------------------------------------------------------------------------
# Overlay
# -------------------------------------------------------------------------------------------------

def create_overlay(text):
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=PARAMS.page_format)

    can.setFont(PARAMS.font, PARAMS.overlay_font_size)
    can.setStrokeColor(PARAMS.overlay_edgecolor)
    can.setFillColor(PARAMS.overlay_bgcolor)
    can.setFillAlpha(PARAMS.overlay_opacity)
    can.rect(
        PARAMS.overlay_x, PARAMS.overlay_y,
        PARAMS.overlay_w, PARAMS.overlay_h, fill=1)
    can.setFillColor(PARAMS.overlay_textcolor)

    # print(text)
    can.drawString(PARAMS.overlay_x_text, PARAMS.overlay_y_text, text)
    can.save()
    packet.seek(0)
    reader = PdfReader(packet)
    reader.packet = packet
    reader.canvas = canvas
    return reader


# -------------------------------------------------------------------------------------------------
# Main functions
# -------------------------------------------------------------------------------------------------

def add_overlay(page, name, n=0):
    page_number = f"p. {n} {'—' if name else ''} {name}"
    overlay = create_overlay(page_number)
    page.merge_page(overlay.get_page(0))
    return page_number


def collate_pdfs(file_paths, output_pdf, first_page=1):
    toc = []
    cur_page = first_page
    # left = None

    for file_path, pdf_reader in iter_files(file_paths):
        n = cur_page + 1

        # # HACK: force the next item to start on the left page.
        # if not left:
        #     left = file_path == "LEFT"
        #     if left:
        #         continue

        # Blank page
        if not file_path:
            output_pdf.add_blank_page()
            cur_page += 1
            n += 1

        # Divider page.
        elif not pdf_reader:
            toc_entry = file_path[1:].strip()

            cur_page += ensure_even_pages(output_pdf)
            n = cur_page + 1

            # Create the divider page.
            with make_canvas() as canvas:
                create_divider(canvas, toc_entry)

            # Add the overlay
            page = canvas.pdf.get_page(0)
            add_overlay(page, "", n=n)

            # Insert the divider page.
            output_pdf.add_page(page)

            # Generate the TOC entry.
            toc.append("")
            toc.append(f"p. {n:d} — {toc_entry}")

            # HACK: if "LEFT" is set, force the item to start on the left page.
            # if not left:
            # cur_page += ensure_even_pages(output_pdf)
            # else:
            #     left = None

            cur_page += 1

        # PDF to collate.
        else:
            pretty_name = get_pretty_name(file_path, replace_slashes=True)
            num_pages = pdf_reader.get_num_pages()

            # Add TOC entry
            toc.append(f"p. {n:d} — {pretty_name}")

            # Add all pages of the current PDF.
            for i in range(num_pages):
                n = cur_page + i + 1
                page = resize_page(pdf_reader.get_page(i), PARAMS.page_format)
                add_overlay(page, pretty_name, n=n)
                output_pdf.add_page(page)
            cur_page += num_pages

            # # HACK: if "LEFT" is set, force the item to start on the left page.
            # if not left:
            #     cur_page += ensure_even_pages(output_pdf)
            # else:
            #     left = None

    return toc


def main():

    parser = argparse.ArgumentParser(description="Collate PDF tool")
    subparsers = parser.add_subparsers(dest='command')

    # makeindex command
    parser_makeindex = subparsers.add_parser(
        'makeindex', help='Create index file')
    parser_makeindex.add_argument('input', nargs='+', help='Input PDF files')
    parser_makeindex.add_argument(
        '-o', '--output', required=False, help='Output index file')

    # makepdf command
    parser_makepdf = subparsers.add_parser(
        'makepdf', help='Create collated PDF')
    parser_makepdf.add_argument('index', help='Index file')
    parser_makepdf.add_argument(
        '-o', '--output', required=False, help='Output collated PDF file')
    parser_makepdf.add_argument(
        '-c', '--cover', required=False, help='Cover PDF file')
    parser_makepdf.add_argument(
        '-f', '--font', required=False, help='Path to a TTF font')
    parser_makepdf.add_argument(
        '-d', '--duplex', required=False, action='store_true',
        help='Adapt to double-sided printing')

    args = parser.parse_args()

    if args.command == 'makeindex':

        make_index(args.input, args.output or PARAMS.index_file)

    elif args.command == 'makepdf':

        # Get the paths to the PDFs to collate from the index.
        file_paths = parse_index(args.index)

        # Font.
        if args.font:
            if not op.exists(args.font):
                raise ValueError(f"Path `{args.font}` does not exist.")
            set_font(args.font)

        # Duplex printing.
        PARAMS.duplex = args.duplex

        # Create the final writer.
        output_pdf_with_toc = PdfWriter()

        # Add the cover page.
        first_page = 1
        cover_file = args.cover or PARAMS.cover_file
        if cover_file:
            first_page += append_pdf(output_pdf_with_toc, cover_file)
            ensure_even_pages(output_pdf_with_toc)

        # Create the writer.
        output_pdf = PdfWriter()

        # Collate all PDFs and generate the TOC.
        toc = collate_pdfs(file_paths, output_pdf, first_page=first_page)

        # Create the TOC page.
        with make_canvas() as page:
            create_toc(page, toc)
        toc_pdf = page.pdf

        # Add the TOC.
        append_pdf(output_pdf_with_toc, toc_pdf)
        ensure_even_pages(output_pdf_with_toc)

        # Add the collated PDFs.
        append_pdf(output_pdf_with_toc, output_pdf)

        # Save the PDF to disk.
        write_pdf(output_pdf_with_toc, args.output or PARAMS.output_file)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
