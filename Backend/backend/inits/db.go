package inits

import (
	//"fmt"
	"log"
	"os"

	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

var DB *gorm.DB

func DBInit() {
	var err error
	dsn := os.Getenv("DB_URL")
	if dsn == "" {
		log.Fatal("DB_URL environment variable is not set")
	}

	DB, err = gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		log.Fatal("failed to connect database, got error", err)
	}
}

/*

import (
    "gorm.io/driver/postgres"
    "gorm.io/gorm"
)

dsn := os.Getenv("DB_URL")
db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})


*/