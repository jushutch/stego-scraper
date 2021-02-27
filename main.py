#!/usr/bin/env python

import sys
import os
from bs4 import BeautifulSoup
import urllib.request
import urllib.parse
import requests
import shutil
import binwalk
import string
import re
import getopt

GET_IMAGE_OPTIONS = [
    {'tag': 'img',
     'attr': 'src',
     'attr_filters': {}
     },
    {'tag': 'link',
     'attr': 'href',
     'attr_filters': {"type": "image/png"}
     },
]


def get_images(url: urllib.parse.ParseResult, directory: str, absolute_image_url: bool) -> int:
    html_page = urllib.request.urlopen(url.geturl())
    soup = BeautifulSoup(html_page, features="html.parser")
    for options in GET_IMAGE_OPTIONS:
        for image_data, file_name in get_images_from_soup_by_type(soup, options, absolute_image_url, url):
            with open(os.path.join(directory, file_name), 'wb') as file:
                shutil.copyfileobj(image_data, file)
    return len(os.listdir(directory))


def get_images_from_soup_by_type(soup: BeautifulSoup, options: dict, absolute_image_url: bool, url: urllib.parse.ParseResult):
    for image in soup.find_all(options['tag'], recursive=True, attrs=options['attr_filters']):
        image_path = image.get(options['attr'])
        if absolute_image_url:
            image_url = image_path
        else:
            image_url = url.scheme + '://' + url.hostname + '/' + image_path
        response = requests.get(image_url, stream=True)
        image_file_name = os.path.basename(urllib.parse.urlparse(image_url).path)
        yield response.raw, image_file_name


def extract_hidden_files(directory: str):
    for filename in os.listdir(directory):
        binwalk.scan(os.path.join(directory, filename), quiet=True, signature=True, rm=True, extract=True,
                     directory=directory)


def strings(filename, min=4):
    with open(filename, errors="ignore") as f:
        result = ""
        for c in f.read():
            if c in string.printable:
                result += c
                continue
            if len(result) >= min:
                yield result
            result = ""
        if len(result) >= min:
            yield result


def search_for_flags(directory: str, flag_prefix: str) -> list:
    flags_found = []
    for currentpath, folders, files in os.walk(directory):
        for file in files:
            sl = list(strings(os.path.join(currentpath, file)))
            flag = [extract_flag_from_string(i, flag_prefix) for i in sl if flag_prefix in i]
            if len(flag) > 0:
                hidden = False
                if "extracted" in currentpath:
                    hidden = True
                flags_found.append({
                    "flag": flag.pop(),
                    "filename": file,
                    "hidden": hidden
                })
    return flags_found


def print_results(flags: list, number_of_images: int):
    print(f"Images scanned: {number_of_images}")
    print(f"Flags found: {len(flags)}\n")
    print_flags(flags)


def print_flags(flags: list):
    print(f"{'Filename' : <20}\t{'Hidden' : <10}\t{'Flag' : <30}")
    for flag in flags:
        print(f"{flag['filename'] : <20}\t{'Y' if flag['hidden'] else 'N' : <10}\t{flag['flag'] : <30}")


def extract_flag_from_string(string: str, flag_prefix: str) -> str:
    return re.findall(rf"{re.escape(flag_prefix)}{{.*}}", string).pop()


def get_config_from_command_line(args: list) -> dict:
    try:
        options, remaining_arguments = getopt.getopt(sys.argv[1:], 'ad:', ['absolute-image-url', 'directory='])
    except getopt.GetoptError:
        print(f"usage: {sys.argv[0]} --absolute-image-url --directory <directory name> <url> <flag prefix>")
        sys.exit(-1)

    absolute_image_url = False
    directory = "temp_dir"
    for option, argument in options:
        if option in "-a" or option in "--absolute-image-url":
            absolute_image_url = True
        elif option in '-d' or option in '--directory':
            directory = argument
    url = urllib.parse.urlparse(remaining_arguments[0])
    flag_prefix = remaining_arguments[1]
    return {'directory': directory, 'url': url, 'absolute_image_url': absolute_image_url, 'flag_prefix': flag_prefix}


def make_temp_directory(directory: str) -> None:
    try:
        os.mkdir(directory)
    except OSError as error:
        print(f"There was a problem creating the directory {directory}:\n{error}", file=sys.stderr)
        sys.exit(-1)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} <options> <url> <flag prefix>", file=sys.stderr)
        sys.exit(-1)

    config = get_config_from_command_line(sys.argv)
    make_temp_directory(config['directory'])
    number_of_images = get_images(config['url'], config['directory'], config['absolute_image_url'])
    extract_hidden_files(config['directory'])
    flags = search_for_flags(config['directory'], config['flag_prefix'])
    print_results(flags, number_of_images)
    shutil.rmtree(config['directory'])
