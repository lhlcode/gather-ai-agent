package com.example.ticket_booking.event;

public class EventSummary {
    private Long id;
    private String title;
    private int totalQuota;
    private int availableQuota;
    private String registrationStartAtUtc;
    private String registrationEndAtUtc;

    public String getRegistrationStartAtUtc() {
        return registrationStartAtUtc;
    }

    public void setRegistrationStartAtUtc(String registrationStartAtUtc) {
        this.registrationStartAtUtc = registrationStartAtUtc;
    }

    public String getRegistrationEndAtUtc() {
        return registrationEndAtUtc;
    }

    public void setRegistrationEndAtUtc(String registrationEndAtUtc) {
        this.registrationEndAtUtc = registrationEndAtUtc;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public int getTotalQuota() {
        return totalQuota;
    }

    public void setTotalQuota(int totalQuota) {
        this.totalQuota = totalQuota;
    }

    public int getAvailableQuota() {
        return availableQuota;
    }

    public void setAvailableQuota(int availableQuota) {
        this.availableQuota = availableQuota;
    }
}