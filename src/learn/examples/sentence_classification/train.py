# -*- coding: utf-8 -*-
import os
import sys
import torch
import torch.autograd as autograd
import torch.nn.functional as F


def train(train_iter, dev_iter, model, args):
    """
    :param train_iter:
    :param dev_iter:
    :param model:
    :param args:
    :return:
    """
    if args.cuda:
        model.cuda()

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    steps = 0
    best_acc = 0
    last_step = 0
    model.train()

    for epoch in range(1, args.epochs+1):
        for batch in train_iter:
            feature, target = batch.text, batch.label
            # batch_first, index align
            feature.data.t_(), target.data.sub_(1)
            if args.cuda:
                feature, target = feature.cuda(), target.cuda()

            optimizer.zero_grad()

            logit = model(feature)
            loss = F.cross_entropy(logit, target)
            loss.backward()
            optimizer.step()

            steps += 1
            if steps % args.log_interval == 0:
                corrects = (torch.max(logit, 1)[1].view(target.size()).data == target.data).sum()
                accuracy = 100.0 * corrects / args.batch_size
                print("\r Epoch {}, Batch[{}] - loss: {: .6f}  acc: {: .4f}%({}/{})".format(epoch, steps,
                                                                                 loss.data[0],
                                                                                 accuracy,
                                                                                 corrects,
                                                                                 args.batch_size))
            if steps % args.test_interval == 0:
                dev_acc = eval(dev_iter, model, args)
                if dev_acc > best_acc:
                    best_acc = dev_acc
                    last_step = steps
                    if args.save_best:
                        save(model, args.save_dir, 'best', steps)
                else:
                    if steps - last_step >= args.early_stop:
                        print("early stop by {} steps".format(args.early_stop))
            elif steps % args.save_interval == 0:
                save(model, args.save_dir, 'snapshot', steps)


def eval(data_iter, model, args):
    """
    :param data_iter:
    :param model:
    :param args:
    :return:
    """
    model.eval()
    corrects, avg_loss = 0, 0.
    for batch in data_iter:
        feature, target = batch.text, batch.label
        # batch_first, index align
        feature.data.t_(), target.data.sub_(1)
        if args.cuda:
            feature, target = feature.cuda(), target.cuda()

        logit = model(feature)
        loss = F.cross_entropy(logit, target, size_average=False)

        corrects += (torch.max(logit, 1)[1].view(target.size()).data == target.data).sum()
        avg_loss += loss.data[0]

    size = len(data_iter.dataset)
    avg_loss /= size
    accuracy = 100.0 * corrects/size
    print("Evaluation - loss: {:.6f}  acc: {: .4f}%({}{}) \n".format(avg_loss, accuracy, corrects, size))
    return accuracy


def predict(text, model, text_field, label_field, cuda_flag):
    """
    :param text:
    :param model:
    :param text_field:
    :param label_field:
    :param cuda_flag:
    :return:
    """
    assert isinstance(text, str)
    model.eval()
    text = text_field.preprocess(text)
    text = [[text_field.vocab.stoi[x] for x in text]]
    x = text_field.tensor_type(text)
    x = autograd.Variable(x, volatile=True)
    if cuda_flag:
        x = x.cuda()
    print(x)
    output = model(x)
    _, predicted = torch.max(output, 1)
    return label_field.vocab.itos[predicted.data[0]+1]


def save(model, save_dir, save_prefix, steps):
    """
    :param model:
    :param save_dir:
    :param save_prefix:
    :param steps:
    :return:
    """
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir)
    save_prefix = os.path.join(save_dir, save_prefix)
    save_path = "{}_steps_{}.pt".format(save_prefix, steps)
    torch.save(model.state_dict(), save_path)