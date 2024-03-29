import cv2
import tensorflow as tf
from mrcnn import model as modellib
import visiope_full_ALCORLAB
import pickle
import os
import json
from scipy import sparse
import numpy as np

def encode_mask(mask):
        
    #ENCODING
    encoded_list= [mask.shape]
    flag = True
    
    for k in np.arange(mask.shape[2]):
        for j in np.arange(mask.shape[1]):
            for i in np.arange(mask.shape[0]):
                if mask[i,j,k] and flag:
                    flag = False
                    encoded_list.append([i,j,k,1])
                else:
                    if mask[i,j,k]:
                        encoded_list[len(encoded_list)-1][3]+=1
                    else:
                        flag = True
                    
    return encoded_list
    
def decode_mask(encoded_list):
    
    #DECODING    
    decoded_mask = np.zeros(encoded_list[0], dtype=bool)
    encoded_list.pop(0)
    
    for element in encoded_list:
        for i in np.arange(element[3]):
            decoded_mask[element[0]+i,element[1],element[2]]=True
    
    return decoded_mask


def video_to_detection(model, video_relative, video_folder, video_name, class_id, annotations):
        
    # Video capture
    video_path = video_relative+'/'+video_folder+'/'+video_name
    vcapture = cv2.VideoCapture(video_path)
    fps = vcapture.get(cv2.CAP_PROP_FPS)
    orig_n_frames = int(vcapture.get(cv2.CAP_PROP_FRAME_COUNT))
    
    #get segments from video
    curr_ann = annotations['database'][video_name[:video_name.find('.')]]['annotations']
    
    dataset_segments = {}
    counter = 0
    
    n_tot_segment_frame=0
    for j in curr_ann:
        segment_time = int(j['segment'][1] - j['segment'][0])	
        
        segment_start_frame= int(j['segment'][0])*fps                
        segment_frame = fps*segment_time
        dataset_segments[counter] = {}
        dataset_segments[counter]['segment_start_frame'] = segment_start_frame
        dataset_segments[counter]['segment_n_frame'] = segment_frame
        n_tot_segment_frame = n_tot_segment_frame+segment_frame
        counter+=1
    
    
    print(video_path)
    print("n video frame: %d" % orig_n_frames)
    print("fps: %d" % fps)
    print("n segment: %d" % len(dataset_segments))
    print("n tot segment frame: %d" % n_tot_segment_frame)
    


    
    segments = {}
    for i in dataset_segments:
        
        n_frames = dataset_segments[i]['segment_n_frame']
        start_frame = dataset_segments[i]['segment_start_frame']

        segments[i] ={
                      'n_frames': n_frames,
                      'frames_info':[]
                     }
    
        success = True
        count=0
        curr_frame_index = start_frame
        while success and (count<n_frames):
            print("frame: %d / %d" % ((count+1), n_frames))
            print("segment: %d / %d" % ((i+1),len(dataset_segments)))
            # Read next image
            vcapture.set(1,curr_frame_index)
            success, image = vcapture.read()
            if success:
                # OpenCV returns images as BGR, convert to RGB
                image = image[..., ::-1]
                # Detect objects
                r = model.detect([image], verbose=0)[0]
                
                print("objs: %d" % len(r['rois']))
    
                if len(r['class_ids']) > 0:
                    encoded_list=encode_mask(r['masks'])
                    segments[i]['frames_info'].append({'original_index':curr_frame_index,
                                                       'obj_class_ids':r['class_ids'],
                                                       'obj_rois':r['rois'],
                                                       'obj_masks':encoded_list})
                count += 1
                curr_frame_index+=1
    


    video_info = {'video_name': video_name,
                  'class_id': video_folder,
                  'fps': fps,
                  'original_nframes':orig_n_frames, 
                  'segments_nframes':n_tot_segment_frame,
                  'n_segments': len(dataset_segments)}               
    
    video_info['segments'] = segments

    return video_info


def main():

    # CONFIG
    #--------------------------------------------------------------------
    config = visiope_full_ALCORLAB.VisiopeConfig()

    # Override the training configurations with a few
    # changes for inferencing.
    class InferenceConfig(config.__class__):
        # Run detection on one image at a time
        GPU_COUNT = 1
        IMAGES_PER_GPU = 1
        DETECTION_MIN_CONFIDENCE = 0.6

    config = InferenceConfig()
    #config.display()
    DEVICE = "/gpu:0"  # /cpu:0 or /gpu:0 



    # MODEL
    #---------------------------------------------------------------------
    # Create model in inference mode
    MODEL_DIR= "./logs_VF"

    with tf.device(DEVICE):
        model = modellib.MaskRCNN(mode="inference", model_dir=MODEL_DIR,
                                  config=config)




    # LOAD CHKPT
    #----------------------------------------------------------------------------------
    weights_path = "./logs_VF/visiope20180707T0933/mask_rcnn_visiope_0090.h5"
    print("Model weights path: ", weights_path)
    model.load_weights(weights_path, by_name=True)




    from pydrive.auth import GoogleAuth
    from pydrive.drive import GoogleDrive
    drive = pickle.load(open('auth.pickle','rb'))
    tgt_folder_id_trimmedpickle = '1apTnIAoFV_4f2VG8id9OaY7-Jalxmuty'
    tgt_folder_id_txt = '1wErTHdRuaRLR2Znd4_ayvmsdpE-DRJt0'
    

    



    # VIDEO DETECTION
    #--------------------------------------------------------------------------------
    video_relative = r'../Train_Eval_ActivityRecoLSTM/PersonalCare'

    #video_folders = sorted(os.listdir(video_relative))
    #classlbl_to_id = {classlbl:id_ for id_,classlbl in enumerate(video_folders)}
    
    #load the annotations
    annotations = json.load(open(r'../Train_Eval_ActivityRecoLSTM/activity_net.v1-3.min.json','r'))

    temp = [i for i in os.listdir(video_relative) if 'pickle' != i]
    for video_folder in temp:
        
        txt_title = [i for i in os.listdir(video_relative+'/'+video_folder) if i[0]=='_'][0]
        print(txt_title)
        file_list = drive.ListFile({'q': "'1wErTHdRuaRLR2Znd4_ayvmsdpE-DRJt0' in parents and trashed=false"}).GetList()
        
        for file in file_list:
            if file['title'] == txt_title:
                txt_id = file['id']
        
        with open(video_relative+'/'+video_folder+'/'+txt_title, 'r') as txt:
            video_in_txt = txt.readlines()
            video_in_txt = [i[:i.find("\\")] for i in video_in_txt]
            
            print(len(video_in_txt))
            print(video_in_txt)

            video_remained_in_txt = list(video_in_txt)

        
        for video_name in video_in_txt:
            video_info = video_to_detection(model,
                                            video_relative, 
                                            video_folder, 
                                            video_name, 
                                            video_folder,
                                            annotations)


            video_name = video_name[:video_name.find('.')]
            pickle.dump(video_info, open(video_relative+'/'+video_folder+'/'+video_name+'_trimmed.pickle','wb'))
            
            file = drive.CreateFile({'title':video_name+'_trimmed.pickle',
                                     'parents':[{"kind": "drive#fileLink","id": tgt_folder_id_trimmedpickle}]})
            file.SetContentFile(video_relative+'/'+video_folder+'/'+video_name+'_trimmed.pickle')
            file.Upload() 


            video_remained_in_txt = [i for i in video_remained_in_txt if video_name not in i]
            print(len(video_remained_in_txt))
            print(video_remained_in_txt)

            with open(txt_title,'w') as txt:
                for i in video_remained_in_txt:
                    txt.write(i+'\n')


            file_txt = drive.CreateFile({'title':txt_title, 'id':txt_id,
                                         'parents':[{"kind": "drive#fileLink","id": tgt_folder_id_txt}]}) 
            file_txt.SetContentFile(txt_title)
            file_txt.Upload() 

            print(video_name+' dumped')


main()