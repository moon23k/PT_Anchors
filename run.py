import numpy as np
import os, random, argparse

import torch
import torch.nn as nn
import torch.optim as optim
import torch.backends.cudnn as cudnn

from module.test import Tester
from module.train import Trainer
from module.data import load_dataloader

from transformers import (set_seed,
                          T5Config, 
                          LongT5Config, 
                          T5TokenizerFast
                          T5ForConditionalGeneration, 
                          LongT5ForConditionalGeneration)




def load_model(config):
    if config.mode == 'train':

        if config.task == 'sum':
            model = LongT5ForConditionalGeneration.from_pretrained(config.m_name)
        else:
            model = T5ForConditionalGeneration.from_pretrained(config.m_name)
        
        print("Pretrained T5 Model has loaded")
    
    elif config.mode != 'train':
        assert os.path.exists(config.ckpt)
        
        if config.task == 'sum':
            model_config = LongT5Config.from_pretrained(config.m_name)
            model = T5ForConditionalGeneration(model_config)
        else:
            model_config = T5Config.from_pretrained(config.m_name)
            model = T5ForConditionalGeneration(model_config)
        print("Initialized T5-Small Model has loaded")
        model_state = torch.load(config.ckpt, map_location=config.device)['model_state_dict']
        model.load_state_dict(model_state)
        print(f"Trained Model states has loaded from {config.ckpt}")

    def count_params(model):
        params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        return params
        
    def check_size(model):
        param_size, buffer_size = 0, 0

        for param in model.parameters():
            param_size += param.nelement() * param.element_size()
        
        for buffer in model.buffers():
            buffer_size += buffer.nelement() * buffer.element_size()

        size_all_mb = (param_size + buffer_size) / 1024**2
        return size_all_mb

    print(f"--- Model Params: {count_params(model):,}")
    print(f"--- Model  Size : {check_size(model):.3f} MB\n")
    return model.to(config.device)


class Config(object):
    def __init__(self, args):    
        self.task = args.task
        self.mode = args.mode
        self.ckpt = f"ckpt/{self.task}.pt"

        self.clip = 1
        self.n_epochs = 10
        self.batch_size = 128
        self.learning_rate = 5e-5
        self.iters_to_accumulate = 4

        if self.task == 'sum':
            self.m_name = "google/long-t5-tglobal-base"
        else:
            self.m_name = 't5-base'

        use_cuda = torch.cuda.is_available()
        if use_cuda:
            self.device_type = 'cuda'
        else:
            self.device_type = 'cpu'

        if self.task == 'inference':
            self.device = torch.device('cpu')
        else:
            self.device = torch.device('cuda' if use_cuda else 'cpu')


    def print_attr(self):
        for attribute, value in self.__dict__.items():
            print(f"* {attribute}: {value}")



def inference(config, model, tokenizer):
    print(f'--- Inference Process Started! ---')
    print('[ Type "quit" on user input to stop the Process ]')
    
    while True:
        input_seq = input('\nUser Input Sequence >> ').lower()

        #End Condition
        if input_seq == 'quit':
            print('\n--- Inference Process has terminated! ---')
            break        

        #convert user input_seq into model input_ids
        input_ids = tokenizer(input_seq)

        #Search Output Sequence
        if config.search_method == 'beam':
            output_seq = model.beam_search(input_ids)
        else:
            output_seq = model.greedy_search(input_ids)
        print(f"Model Out Sequence >> {output_seq}")       



def main(args):
    set_seed(42)
    config = Config(args)
    model = load_model(config)

    setattr(config, 'pad_id', model.config.pad_token_id)
    setattr(config, 'max_length', model.config.max_length)
    setattr(config, 'num_beams', model.config.num_beams)


    if config.mode == 'train':
        train_dataloader = load_dataloader(config, 'train')
        valid_dataloader = load_dataloader(config, 'valid')
        trainer = Trainer(config, model, train_dataloader, valid_dataloader)
        trainer.train()
    
    elif config.mode == 'test':
        tokenizer = T5TokenizerFast.from_pretrained('t5-small', model_max_length=512)
        test_dataloader = load_dataloader(config, 'test')
        tester = Tester(config, model, test_dataloader, tokenizer)
        tester.test()
        tester.inference_test()
    
    elif config.mode == 'inference':
        tokenizer = T5TokenizerFast.from_pretrained('t5-small', model_max_length=512)
        translator = inference(config, model, tokenizer)
        translator.translate()
    


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-task', required=True)
    parser.add_argument('-mode', required=True)
    parser.add_argument('-search', default='greedy', required=False)
    
    args = parser.parse_args()
    assert args.task in ['nmt', 'dialog', 'sum']
    assert args.mode in ['train', 'test', 'inference']

    if args.task == 'inference':
        assert args.search in ['greedy', 'beam']

    main(args)