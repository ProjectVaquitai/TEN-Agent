package internal

import (
	"errors"
	"sync"
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
	CreateUser(u *User) error
	UpdateUser(u *User) error
	ArchiveUser(id string) error
	GetUserByEmail(email string) (*User, error)
	GetUserByID(id string) (*User, error)
	GetUserPreferences(id string) (map[string]string, error)
	SetUserPreference(id, key, value string) error
	DeleteUserPreference(id, key string) error
}

type InMemoryUserStore struct {
	mu    sync.Mutex
	users map[string]*User
}

func NewInMemoryUserStore() *InMemoryUserStore {
	return &InMemoryUserStore{
		users: make(map[string]*User),
	}
}

func (s *InMemoryUserStore) CreateUser(u *User) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, found := s.users[u.ID]; found {
		return errors.New("user already exists")
	}
	s.users[u.ID] = u
	return nil
}

func (s *InMemoryUserStore) UpdateUser(u *User) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, found := s.users[u.ID]
	if !found {
		return errors.New("user not found")
	}
	s.users[u.ID] = u
	return nil
}

func (s *InMemoryUserStore) ArchiveUser(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	user, found := s.users[id]
	if !found {
		return errors.New("user not found")
	}
	user.IsArchived = true
	return nil
}

func (s *InMemoryUserStore) GetUserByEmail(email string) (*User, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, user := range s.users {
		if user.Email == email {
			return user, nil
		}
	}
	return nil, errors.New("user not found")
}

func (s *InMemoryUserStore) GetUserByID(id string) (*User, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	user, found := s.users[id]
	if !found {
		return nil, errors.New("user not found")
	}
	return user, nil
}

func (s *InMemoryUserStore) GetUserPreferences(id string) (map[string]string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	user, found := s.users[id]
	if !found {
		return nil, errors.New("user not found")
	}
	return user.Preferences, nil
}

func (s *InMemoryUserStore) SetUserPreference(id, key, value string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	user, found := s.users[id]
	if !found {
		return errors.New("user not found")
	}
	if user.Preferences == nil {
		user.Preferences = make(map[string]string)
	}
	user.Preferences[key] = value
	return nil
}

func (s *InMemoryUserStore) DeleteUserPreference(id, key string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	user, found := s.users[id]
	if !found {
		return errors.New("user not found")
	}
	delete(user.Preferences, key)
	return nil
}
