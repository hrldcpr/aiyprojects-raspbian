#!/usr/bin/env python3
#
# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Camera image classification demo code.

Runs continuous image detection on the VisionBonnet and prints the object and
probability for top three objects.

Example:
image_classification_camera.py --num_frames 10
"""
import argparse

from aiy.vision.inference import CameraInference
from aiy.vision.models import image_classification
from picamera import PiCamera

import gpiozero
from aiy import pins

RED = gpiozero.LED(pins.PIN_A)
YELLOW = gpiozero.LED(pins.PIN_B)
GREEN = gpiozero.LED(pins.PIN_C)
BLUE = gpiozero.LED(pins.PIN_D)

COMPOST = {
    'banana',
    'plate',
    'bagel/beigel',
    'guacamole',
    'consomme',
    'hot pot/hotpot',
    'trifle',
    'ice cream/icecream',
    'ice lolly/lolly/lollipop/popsicle',
    'French loaf',
    'bagel/beigel',
    'pretzel',
    'cheeseburger',
    'hotdog/hot dog/red hot',
    'mashed potato',
    'head cabbage',
    'broccoli',
    'cauliflower',
    'zucchini/courgette',
    'spaghetti squash',
    'acorn squash',
    'butternut squash',
    'cucumber/cuke',
    'artichoke/globe artichoke',
    'bell pepper',
    'cardoon',
    'mushroom',
    'Granny Smith',
    'strawberry',
    'orange',
    'lemon',
    'fig',
    'pineapple/ananas',
    'banana',
    'jackfruit/jak/jack',
    'custard apple',
    'pomegranate',
    'hay',
    'carbonara',
    'chocolate sauce/chocolate syrup',
    'dough',
    'meat loaf/meatloaf',
    'pizza/pizza pie',
    'potpie',
    'burrito',
}
LANDFILL = {
    'abacus',
    'ballpoint/ballpoint pen/ballpen/Biro',
    'computer keyboard/keypad',
    'desktop computer',
    'fountain pen',
    'laptop/laptop computer',
    'mouse/computer mouse',
    'notebook/notebook computer',
    'plastic bag',
    'running shoe',
    'sandal',
}
PAPER = {
    'envelope',
    'paper towel',
}
RECYCLING = {
    'beer bottle',
    'bottlecap',
    'carton',
    'pop bottle/soda bottle',
    'water bottle',
    'wine bottle',
}

def update_leds(classes):
    (name, prob) = classes[0]
    RED.on() if name in LANDFILL else RED.off()
    YELLOW.on() if name in PAPER else YELLOW.off()
    GREEN.on() if name in COMPOST else GREEN.off()
    BLUE.on() if name in RECYCLING else BLUE.off()

def classes_info(classes, count):
    return ', '.join('%s (%.2f)' % pair for pair in classes[0:count])


def main():
    parser = argparse.ArgumentParser('Image classification camera inference example.')
    parser.add_argument('--num_frames', '-n', type=int, dest='num_frames', default=None,
        help='Sets the number of frames to run for, otherwise runs forever.')
    parser.add_argument('--num_objects', '-c', type=int, dest='num_objects', default=3,
        help='Sets the number of object interences to print.')

    args = parser.parse_args()

    # Forced sensor mode, 1640x1232, full FoV. See:
    # https://picamera.readthedocs.io/en/release-1.13/fov.html#sensor-modes
    with PiCamera(sensor_mode=4, framerate=30) as camera:
        camera.start_preview()

        with CameraInference(image_classification.model()) as inference:
            for result in inference.run(args.num_frames):
                classes = image_classification.get_classes(result)
                print(classes_info(classes, args.num_objects))
                update_leds(classes)

        camera.stop_preview()


if __name__ == '__main__':
    main()
