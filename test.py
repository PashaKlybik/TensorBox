import tensorflow as tf
import os
import json
import subprocess
from scipy.misc import imread, imresize
from scipy import misc
 
from train import build_forward
from utils.annolist import AnnotationLib as al
from utils.train_utils import add_rectangles, rescale_boxes
 
import cv2
import argparse
import random
 
def get_image_dir(args):
    weights_iteration = int(args.weights.split('-')[-1])
    expname = '_' + args.expname if args.expname else ''
    image_dir = '%s/images_%s_%d%s' % (os.path.dirname(args.weights), os.path.basename(os.path.dirname(args.datadir)), weights_iteration, expname)
    return image_dir

def get_results(args, H, data_dir):
    tf.reset_default_graph()
    new_saver = tf.train.import_meta_graph(args.graphfile)
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        new_saver.restore(sess, args.weights)
        x_in = tf.get_collection('placeholders')[0]
        all_vars = tf.get_collection('vars')

        pred_annolist = al.AnnoList()
        
        included_extenstions = ['jpg', 'bmp', 'png', 'gif']
        image_names = [fn for fn in os.listdir(args.datadir) if any(fn.lower().endswith(ext) for ext in included_extenstions)]
        image_dir = get_image_dir(args)
        subprocess.call('mkdir -p %s' % image_dir, shell=True)
        for i in range(len(image_names)):
            image_name = image_names[i]
            if H['grayscale']:
                orig_img = imread('%s/%s' % (data_dir, image_name), mode = 'RGB' if random.random() < H['grayscale_prob'] else 'L')
                if len(orig_img.shape) < 3:
                    orig_img = cv2.cvtColor(orig_img, cv2.COLOR_GRAY2RGB)
            else:
                orig_img = imread('%s/%s' % (data_dir, image_name), mode = 'RGB')
            img = imresize(orig_img, (H["image_height"], H["image_width"]), interp='cubic')
            feed = {x_in: img}
            (np_pred_boxes, np_pred_confidences) = sess.run(all_vars, feed_dict=feed)
            pred_anno = al.Annotation()
            pred_anno.imageName = image_name
            new_img, rects = add_rectangles(H, [img], np_pred_confidences, np_pred_boxes,
                                            use_stitching=True, rnn_len=H['rnn_len'], min_conf=args.min_conf, tau=args.tau, show_suppressed=args.show_suppressed)
       
            pred_anno.rects = rects
            pred_anno.imagePath = os.path.abspath(data_dir)
            pred_anno = rescale_boxes((H["image_height"], H["image_width"]), pred_anno, orig_img.shape[0], orig_img.shape[1], test=True)
            pred_annolist.append(pred_anno)
           
            imname = '%s/%s' % (image_dir, os.path.basename(image_name))
            misc.imsave(imname, new_img)
            if i % 25 == 0:
                print(i)
    return pred_annolist

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', required=True)
    parser.add_argument('--datadir', required=True)
    parser.add_argument('--graphfile', required=True)
    parser.add_argument('--expname', default='')
    parser.add_argument('--gpu', default=0)
    parser.add_argument('--logdir', default='output')
    parser.add_argument('--iou_threshold', default=0.5, type=float)
    parser.add_argument('--tau', default=0.25, type=float)
    parser.add_argument('--min_conf', default=0.5, type=float)
    parser.add_argument('--show_suppressed', default=False, type=bool)
    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu)
    hypes_file = '%s/hypes.json' % os.path.dirname(args.weights)
    with open(hypes_file, 'r') as f:
        H = json.load(f)
    expname = '_' + args.expname  if args.expname else ''
    pred_boxes = '%s%s.json' % (args.weights, expname)
    true_boxes = '%s.gt_%s' % (args.weights, expname)
 
    pred_annolist = get_results(args, H, os.path.dirname(args.datadir))
    pred_annolist.save(pred_boxes)