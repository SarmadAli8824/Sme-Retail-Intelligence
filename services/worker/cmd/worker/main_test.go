package main

import (
	"strings"
	"testing"
)

func TestDigestContainsStoreMetrics(t *testing.T) {
	html := digestHTML(recipient{Name: "Corner Shop"}, digestStats{UnitsSold: 42, LowStock: 3, TotalSKUs: 12})
	for _, value := range []string{"Corner Shop", "42", "3", "12", "weekly shop digest"} {
		if !strings.Contains(html, value) {
			t.Fatalf("digest is missing %q", value)
		}
	}
}

func TestIdentifierIsUnique(t *testing.T) {
	first, second := identifier(), identifier()
	if first == "" || second == "" || first == second {
		t.Fatal("worker identifiers must be non-empty and unique")
	}
}
