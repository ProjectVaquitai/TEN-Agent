package internal

import (
	"context"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

type Session struct {
	Token  string
	UserID string
}

// SessionStore interface for future-proofing
type SessionStore interface {
	CreateSession(ctx context.Context, s *Session) error
	GetSession(ctx context.Context, token string) (*Session, error)
	DeleteSession(ctx context.Context, token string) error
}

type MongoDBSessionStore struct {
	collection *mongo.Collection
}

func NewMongoDBSessionStore(client *mongo.Client, dbName, collectionName string) *MongoDBSessionStore {
	collection := client.Database(dbName).Collection(collectionName)
	return &MongoDBSessionStore{collection: collection}
}

func (store *MongoDBSessionStore) CreateSession(ctx context.Context, s *Session) error {
	_, err := store.collection.InsertOne(ctx, s)
	if err != nil {
		return err
	}
	return nil
}

func (store *MongoDBSessionStore) GetSession(ctx context.Context, token string) (*Session, error) {
	filter := bson.M{"token": token}
	var session Session
	err := store.collection.FindOne(ctx, filter).Decode(&session)
	if err != nil {
		return nil, err
	}
	return &session, nil
}

func (store *MongoDBSessionStore) DeleteSession(ctx context.Context, token string) error {
	filter := bson.M{"token": token}
	_, err := store.collection.DeleteOne(ctx, filter)
	if err != nil {
		return err
	}
	return nil
}
