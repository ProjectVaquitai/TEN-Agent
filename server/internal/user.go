package internal

import (
	"context"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
)

type User struct {
	ID           string
	Name         string
	Email        string
	PasswordHash string
	IsArchived   bool
	Preferences  map[string]string
}

// UserStore interface for future-proofing
type UserStore interface {
	CreateUser(ctx context.Context, u *User) error
	UpdateUser(ctx context.Context, u *User) error
	ArchiveUser(ctx context.Context, id string) error
	GetUserByEmail(ctx context.Context, email string) (*User, error)
	GetUserByID(ctx context.Context, id string) (*User, error)
	GetUserPreferences(ctx context.Context, id string) (map[string]string, error)
	SetUserPreference(ctx context.Context, id, key, value string) error
	DeleteUserPreference(ctx context.Context, id, key string) error
}

type MongoDBUserStore struct {
	collection *mongo.Collection
}

func NewMongoDBUserStore(client *mongo.Client, dbName, collectionName string) *MongoDBUserStore {
	collection := client.Database(dbName).Collection(collectionName)
	return &MongoDBUserStore{collection: collection}
}

func (s *MongoDBUserStore) CreateUser(ctx context.Context, u *User) error {
	_, err := s.collection.InsertOne(ctx, u)
	if err != nil {
		return err
	}
	return nil
}

func (s *MongoDBUserStore) UpdateUser(ctx context.Context, u *User) error {
	filter := bson.M{"id": u.ID}
	update := bson.M{"$set": u}
	_, err := s.collection.UpdateOne(ctx, filter, update)
	if err != nil {
		return err
	}
	return nil
}

func (s *MongoDBUserStore) ArchiveUser(ctx context.Context, id string) error {
	filter := bson.M{"id": id}
	update := bson.M{"$set": bson.M{"isarchived": true}}
	_, err := s.collection.UpdateOne(ctx, filter, update)
	if err != nil {
		return err
	}
	return nil
}

func (s *MongoDBUserStore) GetUserByEmail(ctx context.Context, email string) (*User, error) {
	filter := bson.M{"email": email}
	var user User
	err := s.collection.FindOne(ctx, filter).Decode(&user)
	if err != nil {
		return nil, err
	}
	return &user, nil
}

func (s *MongoDBUserStore) GetUserByID(ctx context.Context, id string) (*User, error) {
	filter := bson.M{"id": id}
	var user User
	err := s.collection.FindOne(ctx, filter).Decode(&user)
	if err != nil {
		return nil, err
	}
	return &user, nil
}

func (s *MongoDBUserStore) GetUserPreferences(ctx context.Context, id string) (map[string]string, error) {
	user, err := s.GetUserByID(ctx, id)
	if err != nil {
		return nil, err
	}
	return user.Preferences, nil
}

func (s *MongoDBUserStore) SetUserPreference(ctx context.Context, id, key, value string) error {
	filter := bson.M{"id": id}
	update := bson.M{"$set": bson.M{"preferences." + key: value}}
	_, err := s.collection.UpdateOne(ctx, filter, update)
	if err != nil {
		return err
	}
	return nil
}

func (s *MongoDBUserStore) DeleteUserPreference(ctx context.Context, id, key string) error {
	filter := bson.M{"id": id}
	update := bson.M{"$unset": bson.M{"preferences." + key: ""}}
	_, err := s.collection.UpdateOne(ctx, filter, update)
	if err != nil {
		return err
	}
	return nil
}
