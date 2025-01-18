package internal

import (
	"context"
	"log/slog"
	"os"

	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

type Prop struct {
	ExtensionName string
	Property      string
}

const (
	// Extension name
	extensionNameAgoraRTC   = "agora_rtc"
	extensionNameAgoraRTM   = "agora_rtm"
	extensionNameHttpServer = "http_server"

	// Property json
	PropertyJsonFile = "./agents/property.json"
	// Token expire time
	tokenExpirationInSeconds = uint32(86400)

	WORKER_TIMEOUT_INFINITY = -1

	MAX_GEMINI_WORKER_COUNT = 3
)

const (
	defaultUserCollection    = "users"
	defaultSessionCollection = "sessions"
)

var (
	logTag = slog.String("service", "HTTP_SERVER")

	// Retrieve parameters from the request and map them to the property.json file
	startPropMap = map[string][]Prop{
		"ChannelName": {
			{ExtensionName: extensionNameAgoraRTC, Property: "channel"},
			{ExtensionName: extensionNameAgoraRTM, Property: "channel"},
		},
		"RemoteStreamId": {
			{ExtensionName: extensionNameAgoraRTC, Property: "remote_stream_id"},
		},
		"BotStreamId": {
			{ExtensionName: extensionNameAgoraRTC, Property: "stream_id"},
		},
		"Token": {
			{ExtensionName: extensionNameAgoraRTC, Property: "token"},
			{ExtensionName: extensionNameAgoraRTM, Property: "token"},
		},
		"WorkerHttpServerPort": {
			{ExtensionName: extensionNameHttpServer, Property: "listen_port"},
		},
	}
)

type Config struct {
	MongoURI          string
	DatabaseName      string
	UserCollection    string
	SessionCollection string
}

func NewMongoClient(ctx context.Context, uri string) (*mongo.Client, error) {
	clientOptions := options.Client().ApplyURI(uri)
	client, err := mongo.Connect(ctx, clientOptions)
	if err != nil {
		return nil, err
	}
	err = client.Ping(ctx, nil)
	if err != nil {
		return nil, err
	}
	return client, nil
}

func LoadConfig() *Config {
	mongoURI := os.Getenv("MONGODB_URI")
	if mongoURI == "" {
		mongoURI = "mongodb://localhost:27017" // default value
	} else {
		slog.Info("MongoDB URI is set", "uri", mongoURI)
	}

	database := os.Getenv("MONGODB_DATABASE")
	if database != "" {
		slog.Info("MongoDB database is set", "database", database)
	} else {
		slog.Warn("MongoDB database is not set, using default value", "database", "ten_agent_local")
		database = "ten_agent_local"
	}

	return &Config{
		MongoURI:          mongoURI,
		DatabaseName:      database,
		UserCollection:    defaultUserCollection,
		SessionCollection: defaultSessionCollection,
	}
}

func InitializeMongoDB(ctx context.Context) (*mongo.Client, *Config, error) {
	config := LoadConfig()
	client, err := NewMongoClient(ctx, config.MongoURI)
	if err != nil {
		return nil, nil, err
	}
	return client, config, nil
}
