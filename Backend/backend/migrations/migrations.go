package main

import (
	"tollbox_be/inits"
	"tollbox_be/models"
)

func init() {
	inits.LoadEnv()
	inits.DBInit()
}

func main() {
	inits.DB.AutoMigrate(&models.User{})
}