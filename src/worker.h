class Worker {
public:
    Worker(int id);
    void start();
    void stop();
    int getId() const;
private:
    int id;
    bool running;
};