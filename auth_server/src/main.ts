import { NestFactory } from '@nestjs/core';
import { SwaggerModule, DocumentBuilder } from '@nestjs/swagger';
import { AppModule } from './app.module';
import { readFileSync } from 'fs';
import { join } from 'path';
import * as dotenv from 'dotenv';

dotenv.config(); // Add this line to load .env file

async function bootstrap() {
  const httpsOptions = {
    key: readFileSync(
      process.env.PRIVATE_KEY_PATH ?? getCertPath('private_key.pem'),
    ),
    cert: readFileSync(
      process.env.PUBLIC_CERT_PATH ?? getCertPath('certificate.pem'),
    ),
    passphrase: process.env.PRIVATE_KEY_PASSPHRASE,
  };

  const app = await NestFactory.create(AppModule, {
    httpsOptions,
  });
  // const app = await NestFactory.create(AppModule);

  const config = new DocumentBuilder()
    .setTitle('Cats example')
    .setDescription('The cats API description')
    .setVersion('1.0')
    .addTag('cats')
    .build();

  const documentFactory = () => SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('swagger', app, documentFactory);

  await app.listen(process.env.PORT ?? 3000);
}

function getCertPath(fileName: string): string {
  return join(__dirname, 'certs', fileName); // Adjusted path for dist folder
}

bootstrap().catch((err) => console.error('Error during bootstrap:', err));
