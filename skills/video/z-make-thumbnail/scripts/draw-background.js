'use strict';

const DOCUMENT_PATH = '/path/to/thumbnail.af';
const LAYER_NAME = '1-variation-name';
const STYLE = { "style": "solid", "background_colors": ["#193843"] };

const { Document } = require('/document.js');
const { AddChildNodesCommandBuilder, InsertionMode } = require('/commands.js');
const { ShapeNodeDefinition, ContainerNodeDefinition, NodeChildType } = require('/nodes.js');
const { ShapeRectangle } = require('/shapes.js');
const { FillDescriptor, GradientFill } = require('/fills.js');
const { GradientFillType } = require('affinity:fills');
const { Colour, Gradient } = require('/colours.js');
const { Rectangle, Transform } = require('/geometry.js');
const { LineStyleDescriptor } = require('/linestyle.js');
const { Selection } = require('/selections.js');
const { BlendMode } = require('affinity:common');

const BACKGROUND_NAME = 'Background';

function colour(hex) {
    const value = parseInt(hex.replace('#', ''), 16);
    return Colour.createRGBA8({ r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255, alpha: 255 });
}

function samePath(a, b) {
    const strip = (path) => String(path).replace(/^\/private\//, '/');
    return strip(a) === strip(b);
}

function findNamed(nodes, name) {
    for (const node of nodes) {
        if (node.userDescription === name) return node;
    }
    return null;
}

function rectangle(x, y, width, height, fill) {
    return ShapeNodeDefinition.create(
        ShapeRectangle.create(),
        new Rectangle(x, y, width, height),
        fill,
        FillDescriptor.createNone(),
        LineStyleDescriptor.createDefault(0),
        null
    );
}

function gradientFill(box) {
    const stops = STYLE.background_colors.map((hex, i) => ({ colour: colour(hex), position: STYLE.gradient_stops[i] / 100 }));
    if (stops[0].position > 0) stops.unshift({ colour: stops[0].colour, position: 0 });
    if (stops[stops.length - 1].position < 1) stops.push({ colour: stops[stops.length - 1].colour, position: 1 });
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    let type;
    let transform;
    if (STYLE.gradient_type === 'radial') {
        const radius = Math.hypot(box.width, box.height) / 2;
        type = GradientFillType.Radial;
        transform = Transform.createTranslate(centerX, centerY).multiply(Transform.createScale(radius, radius));
    } else {
        const angle = STYLE.gradient_angle * Math.PI / 180;
        const length = Math.abs(box.width * Math.cos(angle)) + Math.abs(box.height * Math.sin(angle));
        type = GradientFillType.Linear;
        transform = Transform.createTranslate(centerX - Math.cos(angle) * length / 2, centerY - Math.sin(angle) * length / 2)
            .multiply(Transform.createRotate(angle))
            .multiply(Transform.createScale(length, length));
    }
    return FillDescriptor.create(GradientFill.create(Gradient.create(stops), type), false, transform, BlendMode.Normal, false);
}

function gridShapes(box) {
    const cell = box.width * STYLE.grid_cell_size / 100;
    const lineColour = colour(STYLE.grid_line_color);
    const shapes = [rectangle(box.x, box.y, box.width, box.height, colour(STYLE.background_colors[0]))];
    const lineWidth = (index) => cell * (index % STYLE.grid_major_every === 0 ? STYLE.grid_major_line_width : STYLE.grid_minor_line_width) / 100;
    for (let i = 0; i * cell <= box.width; i++) {
        const width = lineWidth(i);
        shapes.push(rectangle(box.x + i * cell - width / 2, box.y, width, box.height, lineColour));
    }
    for (let i = 0; i * cell <= box.height; i++) {
        const height = lineWidth(i);
        shapes.push(rectangle(box.x, box.y + i * cell - height / 2, box.width, height, lineColour));
    }
    return shapes;
}

function backgroundShapes(box) {
    const colours = STYLE.background_colors.map(colour);
    switch (STYLE.style) {
        case 'solid':
            return [rectangle(box.x, box.y, box.width, box.height, colours[0])];
        case 'gradient':
            return [rectangle(box.x, box.y, box.width, box.height, gradientFill(box))];
        case 'left-right':
            return colours.map((fill, i) => rectangle(box.x + i * box.width / 2, box.y, box.width / 2, box.height, fill));
        case 'quarters':
            return colours.map((fill, i) => rectangle(box.x + i * box.width / 4, box.y, box.width / 4, box.height, fill));
        case 'grid':
            return gridShapes(box);
        default:
            throw new Error('Unknown style: ' + STYLE.style);
    }
}

function addNodes(doc, target, definitions, insertionMode, pixelAligned) {
    const builder = AddChildNodesCommandBuilder.create();
    builder.setInsertionTarget(target);
    builder.setInsertionMode(insertionMode);
    builder.forcePixelAlignment = pixelAligned;
    for (const definition of definitions) builder.addNode(definition);
    doc.executeCommand(builder.createCommand(false, NodeChildType.Main));
}

const doc = Document.all.find((d) => samePath(d.path, DOCUMENT_PATH));
if (!doc) throw new Error('Document is not open: ' + DOCUMENT_PATH);
const layer = findNamed(doc.layers, LAYER_NAME);
if (!layer) throw new Error('Layer not found: ' + LAYER_NAME);

const oldBackground = findNamed(layer.children, BACKGROUND_NAME);
if (oldBackground) doc.deleteSelection(Selection.create(doc, oldBackground));

addNodes(doc, layer, [ContainerNodeDefinition.create(BACKGROUND_NAME)], InsertionMode.Inside_AtFront, false);
const background = findNamed(layer.children, BACKGROUND_NAME);
addNodes(doc, background, backgroundShapes(doc.spreads.first.baseBoxInterface.baseBox), InsertionMode.Inside_AtBack, true);
console.log('Drew a ' + STYLE.style + ' background in ' + LAYER_NAME);
