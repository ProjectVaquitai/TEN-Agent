import { Test, TestingModule } from '@nestjs/testing';
import { AuthController } from './auth.controller';
import { AuthService } from '../services/auth.service';
import {
  LoginDto,
  LogoutDto,
  RefreshTokenDto,
  ValidateTokenDto,
} from 'src/dtos/auth.dtos';

describe('AuthController', () => {
  let authController: AuthController;
  let authService: AuthService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      controllers: [AuthController],
      providers: [
        {
          provide: AuthService,
          useValue: {
            login: jest.fn(),
            logout: jest.fn(),
            refreshToken: jest.fn(),
            validateToken: jest.fn(),
          },
        },
      ],
    }).compile();

    authController = module.get<AuthController>(AuthController);
    authService = module.get<AuthService>(AuthService);
  });

  it('should be defined', () => {
    expect(authController).toBeDefined();
  });

  describe('login', () => {
    it('should return a token on successful login', async () => {
      const result = 'token';
      const loginDto: LoginDto = { username: 'test', hashedPassword: 'test' };
      jest.spyOn(authService, 'login').mockResolvedValue(result);

      expect(await authController.login(loginDto)).toBe(result);
    });

    it('should throw an exception on failed login', async () => {
      const loginDto: LoginDto = { username: 'test', hashedPassword: 'test' };
      jest
        .spyOn(authService, 'login')
        .mockRejectedValue(new Error('Unauthorized'));

      await expect(authController.login(loginDto)).rejects.toThrow(
        'Unauthorized',
      );
    });
  });

  describe('logout', () => {
    it('should return a success message on successful logout', async () => {
      const result = 'success';
      const logoutDto: LogoutDto = { userId: 'token' };
      jest.spyOn(authService, 'logout').mockResolvedValue(result);

      expect(await authController.logout(logoutDto)).toBe(result);
    });

    it('should throw an exception on failed logout', async () => {
      const logoutDto: LogoutDto = { userId: 'token' };
      jest
        .spyOn(authService, 'logout')
        .mockRejectedValue(new Error('Bad Request'));

      await expect(authController.logout(logoutDto)).rejects.toThrow(
        'Bad Request',
      );
    });
  });

  describe('refreshToken', () => {
    it('should return a new token on successful refresh', async () => {
      const result = 'newToken';
      const refreshTokenDto: RefreshTokenDto = { refreshToken: 'refreshToken' };
      jest.spyOn(authService, 'refreshToken').mockResolvedValue(result);

      expect(await authController.refreshToken(refreshTokenDto)).toBe(result);
    });

    it('should throw an exception on failed refresh', async () => {
      const refreshTokenDto: RefreshTokenDto = { refreshToken: 'refreshToken' };
      jest
        .spyOn(authService, 'refreshToken')
        .mockRejectedValue(new Error('Bad Request'));

      await expect(
        authController.refreshToken(refreshTokenDto),
      ).rejects.toThrow('Bad Request');
    });
  });

  describe('validateToken', () => {
    it('should return a success message on valid token', async () => {
      const result = 'valid';
      const validateTokenDto: ValidateTokenDto = { token: 'token' };
      jest.spyOn(authService, 'validateToken').mockResolvedValue(result);

      expect(await authController.validateToken(validateTokenDto)).toBe(result);
    });

    it('should throw an exception on invalid token', async () => {
      const validateTokenDto: ValidateTokenDto = { token: 'token' };
      jest
        .spyOn(authService, 'validateToken')
        .mockRejectedValue(new Error('Unauthorized'));

      await expect(
        authController.validateToken(validateTokenDto),
      ).rejects.toThrow('Unauthorized');
    });
  });
});
