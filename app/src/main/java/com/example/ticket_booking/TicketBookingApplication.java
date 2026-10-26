package com.example.ticket_booking;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class TicketBookingApplication {
	public static void main(String[] args) {
		SpringApplication.run(TicketBookingApplication.class, args);
	}
}