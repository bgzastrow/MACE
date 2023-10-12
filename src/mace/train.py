import numpy    as np

import torch
import torch.nn          as nn
from torch.utils.data    import DataLoader
from torch.optim         import Adam

## own scripts
import dataset  as ds
import plotting  
# import tqdm 


def mse_loss(x, x_hat):
    loss = nn.functional.mse_loss(x_hat, x)
    return loss

def rel_loss(x,x_hat):
    len   = x.shape[1]
    x_0   = x[:,0,:]
    x_hat =x_hat[:,1:,:]
    x = x[:,1:,:]
    eps = 1e-4
    loss  = ((x_hat-x_0+eps**2)/(x-x_0+eps))**2
    return loss.mean()

def combi_loss(x,x_hat):
    mse = mse_loss(x,x_hat)
    rel = rel_loss(x,x_hat)/1.e6
    # print('losses',mse,rel,mse+rel)
    return mse+rel

def loss_function(x,x_hat,type):
    if type == 'mse':
        return mse_loss(x,x_hat)
    if type == 'rel': 
        return rel_loss(x,x_hat)
    if type == 'combi':
        return combi_loss(x,x_hat)


def train_one_epoch(data_loader, model, DEVICE, optimizer, loss_type):
    '''
    Function to train 1 epoch.

    - data_loader   = data, torchtensor
    - model         = ML architecture to be trained
    - loss_type     = type of loss function, string
        Options:
            - 'mse'     : mean squared error loss
            - 'rel'     : relative change in abundance loss
            - 'combi'   : combination of mse & rel loss

    Method:
    1. get data
    2. push it through the model, x_hat = result
    3. calculate loss (difference between x & x_hat), according to loss function defined in loss_function()
    4. with optimiser, get the gradients and update weights using back propagation.
    
    Returns 
    - losses
    '''    
    overall_loss = 0
    status = 0

    for i, (n,p,t) in enumerate(data_loader):

        print('\tbatch',i+1,'/',len(data_loader),end="\r")
        
        n = n.to(DEVICE)     ## op een niet-CPU berekenen als dat er is op de device
        p = p.to(DEVICE) 
        t = t.to(DEVICE)

        if t[-1,-1].item() < 0.011003478870511375:    ## only use data with small dt

            n = torch.swapaxes(n,1,2)

            n_hat, modstatus = model(n[:,0,:],p,t)      
            # print(n[:,0,:])  

            if modstatus.item() == 4:
                # print('stat4')
                status += modstatus.item()

            ## Calculate losses
            loss  = loss_function(n,n_hat, loss_type)
            # print(loss)
            # print(type(loss))
            overall_loss += loss.item()

            ## Backpropagation
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    
        else:           ## else: skip this data
            continue

    return (overall_loss)/(i+1), status  ## save losses
            



def validate_one_epoch(test_loader, model, DEVICE, loss_type):

    overall_loss = 0
    # status = 0

    with torch.no_grad():
        for i, (n,p,t) in enumerate(test_loader):
            # print('\tbatch',i+1,'/',len(test_loader),end="\r")

            n     = n.to(DEVICE)     ## op een niet-CPU berekenen als dat er is op de device
            p     = p.to(DEVICE) 
            t     = t.to(DEVICE)
            
            n = torch.swapaxes(n,1,2)

            n_hat, status = model(n[:,0,:],p,t)         ## output van het autoecoder model

            # if status.item() == 4:
            #     status += 4

            ## Calculate losses
            loss  = loss_function(n,n_hat,loss_type)
            overall_loss += loss.item()

            return (overall_loss)/(i+1)  ## save losses


def train(model, lr, data_loader, test_loader, epochs, DEVICE, loss_type,plot = False, log = True, show = True):
    optimizer = Adam(model.parameters(), lr=lr)

    loss_train_all = []
    loss_test_all  = []
    status_all = []

    print('Model:         ')
    print('learning rate: '+str(lr))
    print('\n>>> Training model...')
    for epoch in range(epochs):

        ## Training
        
        model.train()
        print('')
        train_loss, status = train_one_epoch(data_loader, model, DEVICE, optimizer, loss_type)
        loss_train_all.append(train_loss)  ## save losses
        status_all.append(status%4)

        ## Validating
        # print('\n>>> Validating model...')
        model.eval() ## zelfde als torch.no_grad

        test_loss = validate_one_epoch(test_loader, model, DEVICE, loss_type)
        loss_test_all.append(test_loss)
        
        print("\nEpoch", epoch + 1, "complete!", "\tAverage loss train: ", train_loss, "\tAverage loss test: ", test_loss, end="\r")
    print('\n \tDONE!')

    if plot == True:
        plotting.plot_loss(loss_train_all, loss_test_all, log = log, show = show)

    return loss_train_all, loss_test_all, status_all


def test(model, test_loader, DEVICE, loss_type):
    overall_loss = 0

    print('\n>>> Testing model...')
    count_nan = 0
    with torch.no_grad():
        for i, (n,p,t) in enumerate(test_loader):
            print('\tbatch',i+1,'/',len(test_loader),', # nan',count_nan,end="\r")

            n     = n.to(DEVICE)     ## op een niet-CPU berekenen als dat er is op de device
            p     = p.to(DEVICE) 
            t     = t.to(DEVICE)
            
            n = torch.swapaxes(n,1,2)

            n_hat, status = model(n[:,0,:],p,t)         ## output van het autoecoder model

            if status.item() == 4:
                print('ERROR: neuralODE could not be solved!',i)
                break

            ## Calculate losses
            loss  = loss_function(n,n_hat, loss_type)
            overall_loss += loss.item()

            break
            
    loss = (overall_loss)/(i+1)
    print('\nTest loss:',loss)

    return n, n_hat, t, loss