package main

import (
	"tollbox_be/inits"
	"tollbox_be/routers"
)

func init() {
	inits.LoadEnv()
	inits.DBInit()
}

func main() {
	r := routers.SetupRouter()
	r.Run() 
}
