export class LoginDto {
  username: string;
  hashedPassword: string; // Changed from password to hashedPassword
}

export class LogoutDto {
  userId: string;
}

export class RefreshTokenDto {
  refreshToken: string;
}

export class ValidateTokenDto {
  token: string;
}
