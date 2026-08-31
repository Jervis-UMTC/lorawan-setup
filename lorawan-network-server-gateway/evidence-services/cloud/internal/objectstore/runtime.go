package objectstore

import (
	"errors"
	"strings"
)

type RuntimeSettings struct {
	Backend            string
	FilesystemRoot     string
	AllowDevFilesystem bool
	S3                 S3Settings
}

func NewRuntime(settings RuntimeSettings) (Store, error) {
	switch strings.ToLower(strings.TrimSpace(settings.Backend)) {
	case "filesystem":
		if !settings.AllowDevFilesystem {
			return nil, errors.New("filesystem object store is development-only; explicitly enable it only for isolated smoke testing")
		}
		return NewFilesystem(settings.FilesystemRoot)
	case "s3":
		return NewS3(settings.S3)
	case "":
		return nil, errors.New("object-store backend is required")
	default:
		return nil, errors.New("unsupported object-store backend")
	}
}
