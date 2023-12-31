import torch
from torch.utils.data import DataLoader

from Loader import AirQuality, Traffic, Solar, Activity
from IR_Square_GAIN.structure import Generator, Discriminator

class EXE:
    def __init__(self, args, load=False):
        self.args = args
        self.dict = {'PM25': AirQuality, 'Traffic': Traffic, 'Solar':Solar, 'Activity':Activity}
        if load:
            self.generator = torch.load('Files/IR-Square-GAIN_' + args.dataset + '_' + str(int(args.miss_rate * 10)) + '.pth').to(args.device)
        else:
            self.generator = Generator(args.length, args.length, args.device, args.irm_usage).to(args.device)
        self.discriminator = Discriminator(args.length, args.length).to(args.device)
        self.dataset = self.dict[args.dataset](args.length, 1, args.device, args.r_miss)
        self.criterion = torch.nn.MSELoss()

    def generator_loss(self, x, m):
        x[m == 0] = 0
        x_1 = self.generator(x, m)
        x_impute = x_1.clone()
        x_impute[m == 1] = x[m == 1]
        p = self.discriminator(x_impute, m)
        loss_g = 3 * self.criterion(x_1[m == 1], x[m == 1]) - self.criterion(p, m)
        x_2 = self.generator(x_1, 1 - m)
        return loss_g + 2 * self.criterion(x_2[m == 1], x[m == 1])

    def discriminator_loss(self, x, m):
        x_impute = self.generator(x, m)
        x_impute[m == 1] = x[m == 1]
        p = self.discriminator(x_impute, m)
        return self.criterion(p, m), x_impute

    def run(self):
        mse_loss = torch.nn.MSELoss()
        mae_loss = lambda a, b: torch.mean(torch.abs(a - b))
        optimizer_g = torch.optim.Adam(self.generator.parameters(), lr=self.args.lr)
        optimizer_d = torch.optim.Adam(self.discriminator.parameters(), lr=self.args.lr)
        loader = DataLoader(self.dataset, batch_size=64, shuffle=True)
        for epoch in range(self.args.epochs):
            print('Epoch', epoch)
            mse_error, mae_error, batch_num = 0, 0, 0
            for i, (x, y, m) in enumerate(loader):
                # Training
                optimizer_g.zero_grad()
                loss_g = self.generator_loss(x, m)
                loss_g.backward()
                optimizer_g.step()

                optimizer_d.zero_grad()
                loss_d, result = self.discriminator_loss(x, m)
                loss_d.backward()
                optimizer_d.step()

                # Testing
                mse_error += mse_loss(result[m==0], y[m==0]).item()
                mae_error += mae_loss(result[m==0], y[m==0]).item()
                batch_num += 1
            print('MSE:', round(mse_error / batch_num, 4))
            print('MAE:', round(mae_error / batch_num, 4))
            torch.save(self.generator, 'Files/IR-Square-GAIN_' + self.args.dataset + '_' + str(int(self.args.r_miss * 10)) + '.pth')