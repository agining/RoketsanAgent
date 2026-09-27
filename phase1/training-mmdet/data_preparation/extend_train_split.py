"""Move a fraction of the validation images into the training set.

A random (seeded) ``--fraction`` of the validation images, with all their
annotations, is appended to the training set; the rest stays as the new,
smaller validation set. Image and annotation ids of the moved entries are
renumbered after the training set's ids so they cannot collide.

Example:
    python projects/roketsan/tools/extend_train_split.py \
        ../../dataset/train_coco.json ../../dataset/val_coco.json \
        ../../dataset/train_annotations_extended.json \
        ../../dataset/val_annotations_extended.json
"""
import argparse
import copy
import json
import random
from collections import Counter


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('train_ann')
    parser.add_argument('val_ann')
    parser.add_argument('out_train_ann')
    parser.add_argument('out_val_ann')
    parser.add_argument(
        '--fraction',
        type=float,
        default=0.75,
        help='fraction of validation images moved to the training set')
    parser.add_argument('--seed', type=int, default=0)
    return parser.parse_args()


def summary(name, coco):
    cat_names = {c['id']: c['name'] for c in coco['categories']}
    counts = Counter(cat_names[a['category_id']] for a in coco['annotations'])
    per_class = ', '.join(f'{n} {counts[n]}' for n in cat_names.values())
    print(f'{name}: {len(coco["images"])} images, '
          f'{len(coco["annotations"])} objects ({per_class})')


def main():
    args = parse_args()
    with open(args.train_ann) as f:
        train = json.load(f)
    with open(args.val_ann) as f:
        val = json.load(f)
    assert train['categories'] == val['categories'], 'category mismatch'

    val_images = sorted(val['images'], key=lambda img: img['id'])
    random.Random(args.seed).shuffle(val_images)
    num_moved = round(len(val_images) * args.fraction)
    moved_ids = {img['id'] for img in val_images[:num_moved]}

    # Renumber moved images/annotations after the training set's max ids
    next_img_id = max(img['id'] for img in train['images']) + 1
    next_ann_id = max(ann['id'] for ann in train['annotations']) + 1
    new_img_id = {}
    new_train = copy.deepcopy(train)
    new_val = {k: v for k, v in val.items() if k not in ('images',
                                                         'annotations')}
    new_val['images'], new_val['annotations'] = [], []

    train_names = {img['file_name'] for img in train['images']}
    for img in sorted(val['images'], key=lambda img: img['id']):
        if img['id'] in moved_ids:
            assert img['file_name'] not in train_names, \
                f'{img["file_name"]} is already in the training set'
            new_img_id[img['id']] = next_img_id
            new_train['images'].append(dict(img, id=next_img_id))
            next_img_id += 1
        else:
            new_val['images'].append(img)
    for ann in sorted(val['annotations'], key=lambda ann: ann['id']):
        if ann['image_id'] in moved_ids:
            new_train['annotations'].append(
                dict(ann, id=next_ann_id, image_id=new_img_id[ann['image_id']]))
            next_ann_id += 1
        else:
            new_val['annotations'].append(ann)

    with open(args.out_train_ann, 'w') as f:
        json.dump(new_train, f)
    with open(args.out_val_ann, 'w') as f:
        json.dump(new_val, f)

    summary('original train', train)
    summary('original val  ', val)
    summary('extended train', new_train)
    summary('extended val  ', new_val)
    print(f'Saved to {args.out_train_ann} and {args.out_val_ann}')


if __name__ == '__main__':
    main()
