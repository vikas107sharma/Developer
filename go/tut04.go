// Pipeline pattern 

package main  

import (
	"fmt"
	"time"
)

func sliceToChannel(data []int) <-chan int {
	out := make(chan int)

	go func() {
		defer close(out)
		for _, n := range data {
			out <- n
		}
	}()

	return out
}

func sqNums(dataChannel <-chan int) <-chan int {
	out := make(chan int)

	go func() {
		defer close(out) 
		for n := range dataChannel {
			out <- n*2
		}
	}()

	return out
}

func main() {
	// input 
	data := []int{1,2,3,4} 

	// Stage 1 
	dataChannel := sliceToChannel(data) 

	// Stage 2 
	finalChanel := sqNums(dataChannel)

	// Stage 3
	for n := range finalChanel {
		fmt.Println(n)
	}
}



// buffered  channel 
// here you have to keep the exact size channel so that it will not blocked, len(data) 
// func sliceToChannelBuffered(data []int) <-chan int {
// 	out := make(chan int, len(data))

// 	for _, n := range data {
// 		out <- n // Does not block because buffer size == len(data)
// 	}
// 	close(out)

// 	return out
// }

// unbuffered  channel 
// An unbuffered channel has no storage space.
// out := make(chan int)
// out <- 10 // waits for a receiver