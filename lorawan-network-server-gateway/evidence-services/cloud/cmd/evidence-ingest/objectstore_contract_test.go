package main

import (
	"context"
	"testing"

	"lorawan/evidence-services/cloud/internal/objectstore"
)

func TestObjectStoreContractWriteAndVerify(t *testing.T) {
	store, err := objectstore.NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}
	ctx := context.Background()
	result, err := exerciseObjectStoreWriteContract(ctx, store, "commissioning/objectstore-contract-v1/test-fixture")
	if err != nil {
		t.Fatalf("exerciseObjectStoreWriteContract() error = %v", err)
	}
	if result.Ref == "" || result.SHA256 == "" || result.Size <= 0 || result.RaceRef == "" || result.RaceSHA == "" || result.RaceSize <= 0 {
		t.Fatalf("incomplete result: %+v", result)
	}
	if err := verifyObjectStoreReference(ctx, store, result.Ref, result.SHA256, result.Size); err != nil {
		t.Fatalf("verifyObjectStoreReference() error = %v", err)
	}
}

func TestObjectStoreVerifyRejectsWrongDigest(t *testing.T) {
	store, err := objectstore.NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatalf("NewFilesystem() error = %v", err)
	}
	ctx := context.Background()
	result, err := exerciseObjectStoreWriteContract(ctx, store, "commissioning/objectstore-contract-v1/wrong-digest")
	if err != nil {
		t.Fatalf("exerciseObjectStoreWriteContract() error = %v", err)
	}
	if err := verifyObjectStoreReference(ctx, store, result.Ref, "0000000000000000000000000000000000000000000000000000000000000000", result.Size); err == nil {
		t.Fatal("verifyObjectStoreReference() accepted wrong digest")
	}
}
