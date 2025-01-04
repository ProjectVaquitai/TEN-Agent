package internal

import (
	"errors"
	"sync"
)

type Session struct {
	Token  string
	UserID string
}

// SessionStore interface for future-proofing
type SessionStore interface {
	CreateSession(s *Session) error
	GetSession(token string) (*Session, error)
	DeleteSession(token string) error
}

type InMemorySessionStore struct {
	mu       sync.Mutex
	sessions map[string]*Session
}

func NewInMemorySessionStore() *InMemorySessionStore {
	return &InMemorySessionStore{
		sessions: make(map[string]*Session),
	}
}

func (store *InMemorySessionStore) CreateSession(s *Session) error {
	store.mu.Lock()
	defer store.mu.Unlock()
	store.sessions[s.Token] = s
	return nil
}

func (store *InMemorySessionStore) GetSession(token string) (*Session, error) {
	store.mu.Lock()
	defer store.mu.Unlock()
	session, exists := store.sessions[token]
	if !exists {
		return nil, errors.New("session not found")
	}
	return session, nil
}

func (store *InMemorySessionStore) DeleteSession(token string) error {
	store.mu.Lock()
	defer store.mu.Unlock()
	delete(store.sessions, token)
	return nil
}
